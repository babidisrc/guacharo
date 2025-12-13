import cv2
import numpy as np
import os

# ============================================================================
# 1. VERIFICAÇÃO DE ARQUIVO E INICIALIZAÇÃO
# ============================================================================
# Certifique-se que o caminho está correto
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\Buraco-1.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO FATAL] O arquivo de vídeo não foi encontrado!")
    print(f"O Python procurou em: {CAMINHO_VIDEO}")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

# ============================================================================
# 2. PARÂMETROS DE CALIBRAÇÃO (SEUS VALORES REAIS)
# ============================================================================

# CORES (HSV)
# Amarelo (Piso Tátil)
AMARELO_MIN = np.array([0, 100, 135])
AMARELO_MAX = np.array([30, 255, 255])

# Preto (Buraco) - Calibração da imagem image_9928a7.png
PRETO_MIN = np.array([0, 29, 28])
PRETO_MAX = np.array([179, 102, 100]) # V=100 é crucial para não pegar asfalto

# GEOMETRIA DO "V" (NAVEGAÇÃO)
# Baseado na imagem image_9bd45a.png
W_TOPO_LEVE, W_BASE_LEVE = 40, 42
W_TOPO_BRUSCA, W_BASE_BRUSCA = 95, 38

# GEOMETRIA DE SEGURANÇA
# Ignora os últimos 100px para detecção de buraco (evita detectar o tênis)
ALTURA_IGNORE_PES_BURACO = 100
# Ignora os últimos 70px da linha amarela para calcular curva (olhar p/ horizonte)
ALTURA_IGNORE_PES_NAV = 70
# Zona retangular na base para confirmar se está pisando na linha (200px)
ALTURA_ZONA_CONTATO = 200

# DETECÇÃO DE BURACO
CIRCULARIDADE_MIN = 0.40 # Filtra formas irregulares
AREA_MINIMA_BURACO = 1000 # Ignora sujeirinhas
# Zona de Perigo Central (Onde o robô procura buracos)
LARGURA_BOX_PERIGO = 500 # Bem largo para cobrir a frente toda
ALTURA_BOX_PERIGO = 250

# Variáveis de Estado
ultima_mensagem_nav = "Aguardando..."
ESTA_NA_LINHA = False

# ============================================================================
# 3. FUNÇÕES AUXILIARES
# ============================================================================
def calcular_largura_v(y_atual, y_topo, y_base, w_topo, w_base):
    """Calcula a largura da margem permitida na altura Y (Interpolação Linear)"""
    if y_base == y_topo: return w_base
    # Fator vai de 0.0 (topo) a 1.0 (base)
    fator = (y_atual - y_topo) / (y_base - y_topo)
    return int(w_topo + (w_base - w_topo) * fator)

# ============================================================================
# 4. LOOP PRINCIPAL
# ============================================================================
print(">>> NAVEGADOR VISUAL REVISADO <<<")
print("Legenda: VERDE=Ok | AMARELO=Atenção | VERMELHO=Perigo/Fora")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        # Reinicia o vídeo automaticamente (Loop Infinito)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    # Padronização de Tamanho
    frame = cv2.resize(frame, (600, 400))
    altura, largura, _ = frame.shape
    centro_x = 300
    centro_y = 200 # Metade da altura
    
    # Pré-processamento
    frame_blur = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    
    # Criação das Máscaras Básicas
    mask_amarelo = cv2.inRange(hsv, AMARELO_MIN, AMARELO_MAX)
    mask_buraco = cv2.inRange(hsv, PRETO_MIN, PRETO_MAX)

    # Variáveis de decisão para este frame
    mensagem_central = ""
    cor_texto = (255, 255, 255)
    modo_desvio_ativo = False
    alvo_amarelo_x = None # Onde está o caminho lá na frente?

    # ---------------------------------------------------------------------
    # PASSO 0: MAPEAMENTO DO CAMINHO (Onde está a linha amarela?)
    # ---------------------------------------------------------------------
    # Criamos uma máscara específica para navegação (cortando pés e horizonte)
    mask_nav = mask_amarelo.copy()
    mask_nav[altura-ALTURA_IGNORE_PES_NAV:altura, :] = 0 
    mask_nav[0:100, :] = 0 
    
    contornos_nav, _ = cv2.findContours(mask_nav, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Se achou caminho amarelo, guarda a posição dele (usaremos para desvio)
    if contornos_nav:
        maior_caminho = max(contornos_nav, key=cv2.contourArea)
        if cv2.contourArea(maior_caminho) > 500:
            M = cv2.moments(maior_caminho)
            if M['m00'] != 0:
                alvo_amarelo_x = int(M['m10'] / M['m00'])
                alvo_amarelo_y = int(M['m01'] / M['m00'])
                # Ponto Azul = Destino Ideal
                cv2.circle(frame, (alvo_amarelo_x, alvo_amarelo_y), 6, (255, 0, 0), -1)

    # ---------------------------------------------------------------------
    # PASSO 1: DETECÇÃO DE BURACO (SEGURANÇA - PRIORIDADE MÁXIMA)
    # ---------------------------------------------------------------------
    
    # 1.1 Aplica o Corte dos Pés (Crucial para ignorar tênis)
    mask_buraco[altura-ALTURA_IGNORE_PES_BURACO:altura, :] = 0
    # Linha Cinza = Limite de visão do chão
    cv2.line(frame, (0, altura-ALTURA_IGNORE_PES_BURACO), (largura, altura-ALTURA_IGNORE_PES_BURACO), (100, 100, 100), 1)

    # 1.2 Define a Zona de Perigo (Retângulo Roxo Largo)
    # Centralizado na tela
    box_x1 = centro_x - (LARGURA_BOX_PERIGO // 2)
    box_x2 = centro_x + (LARGURA_BOX_PERIGO // 2)
    box_y1 = centro_y - (ALTURA_BOX_PERIGO // 2) + 50 # +50 para focar mais no chão
    box_y2 = box_y1 + ALTURA_BOX_PERIGO
    
    # Desenha a zona monitorada
    cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (255, 0, 255), 1)

    # 1.3 Análise dos Buracos
    contornos_buraco, _ = cv2.findContours(mask_buraco, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contornos_buraco:
        area = cv2.contourArea(cnt)
        if area > AREA_MINIMA_BURACO:
            
            # Filtro de Circularidade (Ignora formas longas/estranhas)
            perimetro = cv2.arcLength(cnt, True)
            if perimetro == 0: continue
            circularidade = 4 * np.pi * (area / (perimetro * perimetro))
            
            if circularidade > CIRCULARIDADE_MIN:
                x, y, w, h = cv2.boundingRect(cnt)
                cx_buraco = x + w // 2
                cy_buraco = y + h // 2
                
                # O centro do buraco está dentro da Zona Roxa?
                if (box_x1 < cx_buraco < box_x2) and (box_y1 < cy_buraco < box_y2):
                    modo_desvio_ativo = True
                    
                    # Desenha o buraco detectado (Vermelho)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
                    cv2.putText(frame, "PERIGO!", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                    
                    # --- LÓGICA DE DESVIO INTELIGENTE ---
                    # Para onde fugir? Olhe para onde o caminho amarelo foi!
                    if alvo_amarelo_x is not None:
                        if alvo_amarelo_x < centro_x:
                            mensagem_central = "BURACO! DESVIE ESQUERDA <<"
                            # Seta Verde indicando rota de fuga
                            cv2.arrowedLine(frame, (centro_x, 350), (alvo_amarelo_x, 250), (0, 255, 0), 5)
                        else:
                            mensagem_central = "BURACO! DESVIE DIREITA >>"
                            cv2.arrowedLine(frame, (centro_x, 350), (alvo_amarelo_x, 250), (0, 255, 0), 5)
                    else:
                        # Se o buraco tampou o caminho e não vejo amarelo, fujo do centro do buraco
                        if cx_buraco < centro_x:
                            mensagem_central = "PERIGO! DESVIE DIREITA >>"
                        else:
                            mensagem_central = "PERIGO! DESVIE ESQUERDA <<"
                    
                    cor_texto = (0, 0, 255) # Vermelho
                    break # Pare de procurar outros buracos, resolva este primeiro

    # ---------------------------------------------------------------------
    # PASSO 2: NAVEGAÇÃO NORMAL (Se não houver buraco)
    # ---------------------------------------------------------------------
    if not modo_desvio_ativo:
        
        # 2.1 Verificação "Na Linha" (Retângulo de Contato na base)
        # Pega a fatia inferior da imagem
        y_inicio_zona = altura - ALTURA_ZONA_CONTATO
        # Pega uma faixa centralizada de largura 210px
        roi_contato = mask_amarelo[y_inicio_zona:altura, int(centro_x-105):int(centro_x+105)]
        
        # Conta pixels amarelos nos pés
        if cv2.countNonZero(roi_contato) > 5000:
            ESTA_NA_LINHA = True
            # Retângulo Verde na base
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 255, 0), 2)
            cv2.putText(frame, "NA LINHA", (centro_x-45, y_inicio_zona-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            ESTA_NA_LINHA = False
            # Retângulo Vermelho na base
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 0, 255), 2)
            cv2.putText(frame, "FORA", (centro_x-25, y_inicio_zona-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 2.2 Cálculo de Curvas (Geometria em V)
        if alvo_amarelo_x is not None:
            # Usamos o Y do alvo amarelo (aprox) para calcular a largura do V naquele ponto
            cy = alvo_amarelo_y
            
            # Limites do V (Topo=100, Base=400)
            limite_leve = calcular_largura_v(cy, 100, 400, W_TOPO_LEVE, W_BASE_LEVE)
            limite_brusco = calcular_largura_v(cy, 100, 400, W_TOPO_BRUSCA, W_BASE_BRUSCA)
            
            # Desenha as linhas do V para referência
            cv2.line(frame, (centro_x - W_TOPO_BRUSCA, 100), (centro_x - W_BASE_BRUSCA, 400), (0, 255, 255), 1)
            cv2.line(frame, (centro_x + W_TOPO_BRUSCA, 100), (centro_x + W_BASE_BRUSCA, 400), (0, 255, 255), 1)

            # Distância do alvo ao centro da tela
            distancia = abs(alvo_amarelo_x - centro_x)
            
            # Decisão
            if alvo_amarelo_x < centro_x: # Esquerda
                if distancia > limite_brusco: mensagem_central = "Curva Fechada Esquerda <<"
                elif distancia > limite_leve: mensagem_central = "Curva Leve Esquerda <"
                else: mensagem_central = "Continue ^"
            else: # Direita
                if distancia > limite_brusco: mensagem_central = "Curva Fechada Direita >>"
                elif distancia > limite_leve: mensagem_central = "Curva Leve Direita >"
                else: mensagem_central = "Continue ^"
            
            cor_texto = (0, 255, 0)
            ultima_mensagem_nav = mensagem_central # Salva para usar se a visão sumir
            
        else:
            # Não vê caminho à frente
            if ESTA_NA_LINHA:
                # Se pisa no amarelo, mantém a última instrução (Inércia)
                mensagem_central = ultima_mensagem_nav
                cor_texto = (200, 200, 200) # Cinza (Memória)
            else:
                mensagem_central = "FORA DA ROTA - PROCURANDO..."
                cor_texto = (0, 0, 255)

    # ---------------------------------------------------------------------
    # EXIBIÇÃO FINAL
    # ---------------------------------------------------------------------
    # Tarja preta no topo para facilitar leitura do texto
    cv2.rectangle(frame, (0, 0), (600, 80), (0, 0, 0), -1)
    cv2.putText(frame, mensagem_central, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_texto, 2)
    
    cv2.imshow("Navegador Visual Final", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()