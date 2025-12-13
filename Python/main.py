import cv2
import numpy as np
import os
import time

# ============================================================================
# 1. INICIALIZAÇÃO
# ============================================================================
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\CaminhoAmareloBuraco-3.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO FATAL] Vídeo não encontrado!")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

# ============================================================================
# 2. CALIBRAÇÃO (CORES E GEOMETRIA)
# ============================================================================

# --- CORES ---
AMARELO_MIN = np.array([0, 100, 135])
AMARELO_MAX = np.array([30, 255, 255])
PRETO_MIN = np.array([0, 29, 28])
PRETO_MAX = np.array([179, 102, 100])
VERMELHO_MIN = np.array([0, 85, 85])
VERMELHO_MAX = np.array([4, 255, 255])

# --- GEOMETRIA ---
ALTURA_IGNORE_PES_BURACO = 100
ALTURA_IGNORE_PES_OBSTACULO = 60
ALTURA_IGNORE_PES_NAV = 70
ALTURA_ZONA_CONTATO = 200

AREA_MINIMA = 1000
CIRCULARIDADE_BURACO = 0.40 

LARGURA_BOX = 500
ALTURA_BOX = 250

W_TOPO_LEVE, W_BASE_LEVE = 40, 42
W_TOPO_BRUSCA, W_BASE_BRUSCA = 95, 38

# --- NOVO: CONFIGURAÇÃO DE TEMPO ---
TEMPO_MINIMO_PERIGO = 0.5 # Segundos que o objeto deve persistir

# Variáveis de Estado
ultima_mensagem_nav = "Aguardando..."
ESTA_NA_LINHA = False
tempo_inicio_validacao = None # Cronômetro do perigo

# ============================================================================
# 3. FUNÇÕES AUXILIARES
# ============================================================================
def calcular_largura_v(y_atual, y_topo, y_base, w_topo, w_base):
    if y_base == y_topo: return w_base
    fator = (y_atual - y_topo) / (y_base - y_topo)
    return int(w_topo + (w_base - w_topo) * fator)

# ============================================================================
# 4. LOOP PRINCIPAL
# ============================================================================
print(">>> SISTEMA COM VALIDAÇÃO TEMPORAL (0.5s) <<<")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (600, 400))
    altura, largura, _ = frame.shape
    centro_x = 300
    centro_y = 200
    
    # Processamento
    frame_blur = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    
    # Máscaras
    mask_amarelo = cv2.inRange(hsv, AMARELO_MIN, AMARELO_MAX)
    mask_buraco = cv2.inRange(hsv, PRETO_MIN, PRETO_MAX)
    mask_vermelho = cv2.inRange(hsv, VERMELHO_MIN, VERMELHO_MAX)

    mensagem_central = ""
    cor_texto = (255, 255, 255)
    
    # Variáveis temporárias deste frame
    candidato_perigo = False # Detectou algo AGORA?
    dados_perigo = None      # (x, y, w, h, tipo)
    modo_desvio_ativo = False # O perigo foi VALIDADO pelo tempo?
    alvo_amarelo_x = None

    # ---------------------------------------------------------------------
    # PASSO 0: ONDE ESTÁ O CAMINHO?
    # ---------------------------------------------------------------------
    mask_nav = mask_amarelo.copy()
    mask_nav[altura-ALTURA_IGNORE_PES_NAV:altura, :] = 0 
    mask_nav[0:100, :] = 0 
    
    contornos_nav, _ = cv2.findContours(mask_nav, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if contornos_nav:
        maior_caminho = max(contornos_nav, key=cv2.contourArea)
        if cv2.contourArea(maior_caminho) > 500:
            M = cv2.moments(maior_caminho)
            if M['m00'] != 0:
                alvo_amarelo_x = int(M['m10'] / M['m00'])
                alvo_amarelo_y = int(M['m01'] / M['m00'])
                cv2.circle(frame, (alvo_amarelo_x, alvo_amarelo_y), 6, (255, 0, 0), -1)

    # ---------------------------------------------------------------------
    # PASSO 1: DETECÇÃO "CRUA" (SEM VALIDAR TEMPO AINDA)
    # ---------------------------------------------------------------------
    box_x1 = centro_x - (LARGURA_BOX // 2)
    box_x2 = centro_x + (LARGURA_BOX // 2)
    box_y1 = centro_y - (ALTURA_BOX // 2) + 50
    box_y2 = box_y1 + ALTURA_BOX
    
    # Desenha zona monitorada (Cinza clarinho enquanto não tem nada)
    cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (200, 200, 200), 1)

    # 1.1 PROCURA OBSTÁCULO VERMELHO
    mask_vermelho[altura-ALTURA_IGNORE_PES_OBSTACULO:altura, :] = 0
    contornos_verm, _ = cv2.findContours(mask_vermelho, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contornos_verm:
        if cv2.contourArea(cnt) > AREA_MINIMA:
            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            cy = y + h // 2
            if (box_x1 < cx < box_x2) and (box_y1 < cy < box_y2):
                candidato_perigo = True
                dados_perigo = (x, y, w, h, "OBSTACULO")
                break 

    # 1.2 PROCURA BURACO PRETO (Se não achou vermelho)
    if not candidato_perigo:
        mask_buraco[altura-ALTURA_IGNORE_PES_BURACO:altura, :] = 0
        contornos_preto, _ = cv2.findContours(mask_buraco, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contornos_preto:
            if cv2.contourArea(cnt) > AREA_MINIMA:
                perimetro = cv2.arcLength(cnt, True)
                if perimetro == 0: continue
                circularidade = 4 * np.pi * (cv2.contourArea(cnt) / (perimetro * perimetro))
                
                if circularidade > CIRCULARIDADE_BURACO:
                    x, y, w, h = cv2.boundingRect(cnt)
                    cx = x + w // 2
                    cy = y + h // 2
                    if (box_x1 < cx < box_x2) and (box_y1 < cy < box_y2):
                        candidato_perigo = True
                        dados_perigo = (x, y, w, h, "BURACO")
                        break

    # ---------------------------------------------------------------------
    # PASSO 2: VALIDAÇÃO TEMPORAL (0.5 SEGUNDOS)
    # ---------------------------------------------------------------------
    if candidato_perigo:
        # Se é a primeira vez que vejo perigo, inicio o cronômetro
        if tempo_inicio_validacao is None:
            tempo_inicio_validacao = time.time()
        
        # Calculo quanto tempo já passou
        tempo_decorrido = time.time() - tempo_inicio_validacao
        
        x, y, w, h, tipo = dados_perigo
        
        if tempo_decorrido >= TEMPO_MINIMO_PERIGO:
            # --- CONFIRMADO! É UM PERIGO REAL ---
            modo_desvio_ativo = True
            
            # Desenha Vermelho (Perigo Confirmado)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.putText(frame, f"{tipo} CONFIRMADO", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            
            # Muda a cor da zona monitorada para Roxo (Alerta)
            cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (255, 0, 255), 2)
            
        else:
            # --- AINDA VALIDANDO (0.0s a 0.5s) ---
            # Desenha Laranja (Aguardando confirmação)
            # O sistema AINDA NÃO DESVIA, continua seguindo a linha verde
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 165, 255), 2)
            
            # Barra de progresso visual
            progresso = int((tempo_decorrido / TEMPO_MINIMO_PERIGO) * w)
            cv2.rectangle(frame, (x, y+h+5), (x+progresso, y+h+15), (0, 165, 255), -1)
            cv2.putText(frame, "Validando...", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)

    else:
        # Se o perigo sumiu, reseta o cronômetro
        tempo_inicio_validacao = None

    # ---------------------------------------------------------------------
    # PASSO 3: LÓGICA DE NAVEGAÇÃO (DESVIO vs NORMAL)
    # ---------------------------------------------------------------------
    
    # 3.1 MODO DESVIO (SÓ ENTRA AQUI SE PASSOU 0.5s)
    if modo_desvio_ativo:
        tipo = dados_perigo[4]
        
        if alvo_amarelo_x is not None:
            if alvo_amarelo_x < centro_x:
                mensagem_central = f"{tipo}! DESVIE ESQUERDA <<"
                cv2.arrowedLine(frame, (centro_x, 350), (alvo_amarelo_x, 250), (0, 255, 0), 5)
            else:
                mensagem_central = f"{tipo}! DESVIE DIREITA >>"
                cv2.arrowedLine(frame, (centro_x, 350), (alvo_amarelo_x, 250), (0, 255, 0), 5)
        else:
            # Sem visual do caminho, apenas alerta
            mensagem_central = f"{tipo}! PARE AGORA!"
        
        cor_texto = (0, 0, 255)

    # 3.2 MODO NORMAL (NAVEGAÇÃO)
    else:
        # Verificação de Solo
        y_inicio_zona = altura - ALTURA_ZONA_CONTATO
        roi_contato = mask_amarelo[y_inicio_zona:altura, int(centro_x-105):int(centro_x+105)]
        
        if cv2.countNonZero(roi_contato) > 5000:
            ESTA_NA_LINHA = True
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 255, 0), 2)
            cv2.putText(frame, "NA LINHA", (centro_x-45, y_inicio_zona-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            ESTA_NA_LINHA = False
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 0, 255), 2)
            cv2.putText(frame, "FORA", (centro_x-25, y_inicio_zona-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Curvas
        if alvo_amarelo_x is not None:
            cy = alvo_amarelo_y
            limite_leve = calcular_largura_v(cy, 100, 400, W_TOPO_LEVE, W_BASE_LEVE)
            limite_brusco = calcular_largura_v(cy, 100, 400, W_TOPO_BRUSCA, W_BASE_BRUSCA)
            
            # Linhas V
            cv2.line(frame, (centro_x - W_TOPO_BRUSCA, 100), (centro_x - W_BASE_BRUSCA, 400), (0, 255, 255), 1)
            cv2.line(frame, (centro_x + W_TOPO_BRUSCA, 100), (centro_x + W_BASE_BRUSCA, 400), (0, 255, 255), 1)

            distancia = abs(alvo_amarelo_x - centro_x)
            
            if alvo_amarelo_x < centro_x: 
                if distancia > limite_brusco: mensagem_central = "Curva Fechada Esquerda <<"
                elif distancia > limite_leve: mensagem_central = "Curva Leve Esquerda <"
                else: mensagem_central = "Continue ^"
            else: 
                if distancia > limite_brusco: mensagem_central = "Curva Fechada Direita >>"
                elif distancia > limite_leve: mensagem_central = "Curva Leve Direita >"
                else: mensagem_central = "Continue ^"
            
            cor_texto = (0, 255, 0)
            ultima_mensagem_nav = mensagem_central
        else:
            if ESTA_NA_LINHA:
                mensagem_central = ultima_mensagem_nav
                cor_texto = (200, 200, 200)
            else:
                mensagem_central = "PROCURANDO CAMINHO..."
                cor_texto = (0, 0, 255)

    # ---------------------------------------------------------------------
    # EXIBIÇÃO
    # ---------------------------------------------------------------------
    cv2.rectangle(frame, (0, 0), (600, 60), (0, 0, 0), -1)
    cv2.putText(frame, mensagem_central, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor_texto, 2)
    
    cv2.imshow("Navegador com Delay 0.5s", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()