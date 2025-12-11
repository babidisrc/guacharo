import cv2
import numpy as np
import os

# ============================================================================
# 1. CONFIGURAÇÕES
# ============================================================================
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\CaminhoAmareloFalhado-2.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO] Vídeo não encontrado")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

# Cores
amarelo_min = np.array([0, 100, 135])
amarelo_max = np.array([30, 255, 255])
preto_min = np.array([68, 24, 21])
preto_max = np.array([179, 168, 170])

# Geometria do V (Seus valores calibrados)
W_TOPO_LEVE, W_BASE_LEVE = 40, 42
W_TOPO_BRUSCA, W_BASE_BRUSCA = 95, 38

# Altura da zona de verificação dos pés (200px = metade da tela)
ALTURA_ZONA_PES = 200 

# Variáveis de Estado Visual
ultima_direcao_visual = "Aguardando..."
ESTA_NA_LINHA = False

# ============================================================================
# 2. FUNÇÃO AUXILIAR
# ============================================================================
def calcular_limite(y_atual, y_topo, y_base, w_topo, w_base):
    if y_base == y_topo: return w_base
    fator = (y_atual - y_topo) / (y_base - y_topo)
    return int(w_topo + (w_base - w_topo) * fator)

# ============================================================================
# 3. LOOP PRINCIPAL (VISUAL APENAS)
# ============================================================================
print(">>> MODO SILENCIOSO (VISUAL) INICIADO <<<")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (600, 400))
    centro_tela_x = 300
    altura, largura, _ = frame.shape
    
    # Processamento de Imagem
    frame_blur = cv2.GaussianBlur(frame, (5, 5), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    
    mask_amarelo = cv2.inRange(hsv, amarelo_min, amarelo_max)
    mask_buraco = cv2.inRange(hsv, preto_min, preto_max)

    # Variáveis de decisão deste quadro
    mensagem_tela = ""
    cor_texto = (255, 255, 255)
    perigo_buraco = False

    # ---------------------------------------------------------------------
    # PASSO 1: DETECÇÃO DE BURACOS (PRIORIDADE MÁXIMA)
    # ---------------------------------------------------------------------
    contornos_buraco, _ = cv2.findContours(mask_buraco, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contornos_buraco:
        area = cv2.contourArea(cnt)
        if area > 1500: 
            perimetro = cv2.arcLength(cnt, True)
            if perimetro == 0: continue
            circularidade = 4 * np.pi * (area / (perimetro * perimetro))
            if circularidade > 0.4:
                x, y, w, h = cv2.boundingRect(cnt)
                # Só alerta se o buraco estiver na metade de baixo (perto)
                if y + h > 200:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
                    cv2.putText(frame, "PERIGO: BURACO", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                    
                    mensagem_tela = "PARE! BURACO A FRENTE"
                    cor_texto = (0, 0, 255) # Vermelho
                    perigo_buraco = True
                    break

    # ---------------------------------------------------------------------
    # PASSO 2: VERIFICAÇÃO DE POSIÇÃO (NA LINHA / FORA)
    # ---------------------------------------------------------------------
    texto_status_linha = "FORA DA LINHA"
    cor_status_linha = (0, 0, 255)

    if not perigo_buraco:
        y_inicio_zona = altura - ALTURA_ZONA_PES
        # Zona retangular na base
        roi_contato = mask_amarelo[y_inicio_zona:altura, int(centro_tela_x-105):int(centro_tela_x+105)]
        
        if cv2.countNonZero(roi_contato) > 5000:
            ESTA_NA_LINHA = True
            texto_status_linha = "NA LINHA"
            cor_status_linha = (0, 255, 0) # Verde
        else:
            ESTA_NA_LINHA = False
            texto_status_linha = "FORA DA LINHA"
            cor_status_linha = (0, 0, 255) # Vermelho

        # Desenha o retângulo de status na base
        cv2.rectangle(frame, (centro_tela_x-105, y_inicio_zona), (centro_tela_x+105, altura), cor_status_linha, 2)
        cv2.putText(frame, texto_status_linha, (centro_tela_x-100, y_inicio_zona-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_status_linha, 2)

    # ---------------------------------------------------------------------
    # PASSO 3: NAVEGAÇÃO E CURVAS (GEOMETRIA EM V)
    # ---------------------------------------------------------------------
    if not perigo_buraco:
        # Cria máscara de navegação (ignora pés imediatos e horizonte distante)
        mask_nav = mask_amarelo.copy()
        mask_nav[altura-70:altura, :] = 0 
        mask_nav[0:100, :] = 0 

        contornos, _ = cv2.findContours(mask_nav, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if contornos:
            maior_caminho = max(contornos, key=cv2.contourArea)
            if cv2.contourArea(maior_caminho) > 500:
                M = cv2.moments(maior_caminho)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    # Desenha o ponto guia (azul)
                    cv2.circle(frame, (cx, cy), 8, (255, 0, 0), -1)

                    # Cálculos geométricos
                    y_topo_v, y_base_v = 100, 400
                    limite_leve = calcular_limite(cy, y_topo_v, y_base_v, W_TOPO_LEVE, W_BASE_LEVE)
                    limite_brusco = calcular_limite(cy, y_topo_v, y_base_v, W_TOPO_BRUSCA, W_BASE_BRUSCA)

                    # Desenha as linhas do V (Visualização)
                    cv2.line(frame, (centro_tela_x - W_TOPO_LEVE, y_topo_v), (centro_tela_x - W_BASE_LEVE, y_base_v), (255, 0, 0), 1)
                    cv2.line(frame, (centro_tela_x + W_TOPO_LEVE, y_topo_v), (centro_tela_x + W_BASE_LEVE, y_base_v), (255, 0, 0), 1)
                    cv2.line(frame, (centro_tela_x - W_TOPO_BRUSCA, y_topo_v), (centro_tela_x - W_BASE_BRUSCA, y_base_v), (0, 255, 255), 1)
                    cv2.line(frame, (centro_tela_x + W_TOPO_BRUSCA, y_topo_v), (centro_tela_x + W_BASE_BRUSCA, y_base_v), (0, 255, 255), 1)

                    # Decisão de Direção
                    distancia = abs(cx - centro_tela_x)
                    
                    if cx < centro_tela_x: # Esquerda
                        if distancia > limite_brusco:
                            mensagem_tela = "Curva Fechada Esquerda <<"
                            cor_texto = (0, 0, 255)
                        elif distancia > limite_leve:
                            mensagem_tela = "Curva Leve Esquerda <"
                            cor_texto = (0, 255, 255)
                        else:
                            mensagem_tela = "Siga em Frente ^"
                            cor_texto = (0, 255, 0)
                    else: # Direita
                        if distancia > limite_brusco:
                            mensagem_tela = "Curva Fechada Direita >>"
                            cor_texto = (0, 0, 255)
                        elif distancia > limite_leve:
                            mensagem_tela = "Curva Leve Direita >"
                            cor_texto = (0, 255, 255)
                        else:
                            mensagem_tela = "Siga em Frente ^"
                            cor_texto = (0, 255, 0)
                            
                    ultima_direcao_visual = mensagem_tela
        else:
            # Não vê caminho à frente
            if ESTA_NA_LINHA:
                # Se está pisando no amarelo, mantém a última instrução (inércia)
                mensagem_tela = ultima_direcao_visual
            else:
                # Se não vê nada e não pisa em nada
                mensagem_tela = "Procurando caminho..."
                cor_texto = (0, 0, 255)

    # ---------------------------------------------------------------------
    # EXIBIÇÃO FINAL
    # ---------------------------------------------------------------------
    # Escreve a instrução principal no topo da tela
    cv2.putText(frame, mensagem_tela, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_texto, 2)
    
    cv2.imshow("Navegador Visual (Mudo)", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()