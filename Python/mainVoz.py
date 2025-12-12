import cv2
import numpy as np
import pyttsx3
import threading
import queue
import time
import os
import pythoncom # Importante para evitar conflito de threads no Windows

# ============================================================================
# 1. SISTEMA DE ÁUDIO "BLINDADO" (Cria e Destrói o Motor)
# ============================================================================
fila_fala = queue.Queue()

def trabalhador_de_audio():
    # Inicializa contexto COM para thread separada (Correção Windows)
    try:
        pythoncom.CoInitialize()
    except:
        pass

    print("[AUDIO] Thread de voz pronta.")
    
    while True:
        frase = fila_fala.get()
        if frase is None: break
        
        print(f"--> TENTANDO FALAR: {frase}") # Debug Visual
        
        try:
            # ESTRATÉGIA SEGURA: Cria um motor novo para cada frase
            engine = pyttsx3.init()
            engine.setProperty('rate', 220)
            engine.setProperty('volume', 1.0)
            
            engine.say(frase)
            engine.runAndWait()
            
            # Mata o motor para liberar o driver
            del engine
        except Exception as e:
            print(f"[ERRO DE VOZ]: {e}")
        
        fila_fala.task_done()

# Inicia Thread
t = threading.Thread(target=trabalhador_de_audio, daemon=True)
t.start()

def falar(texto, prioridade=False):
    # Se for prioridade, esvazia a fila para falar LOGO
    if prioridade:
        with fila_fala.mutex:
            fila_fala.queue.clear()
    
    # Só adiciona se a fila não estiver cheia (evita delay acumulado)
    if fila_fala.qsize() < 2:
        fila_fala.put(texto)

# ============================================================================
# 2. CONFIGURAÇÕES
# ============================================================================
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\CaminhoAmarelo-3.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO FATAL] Vídeo não encontrado!")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

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

# --- TEMPOS ---
TEMPO_MINIMO_PERIGO = 0.5 

# Estado
ultima_mensagem_falada = ""
tempo_ultima_fala = 0
ESTA_NA_LINHA = False
ULTIMO_ESTADO_LINHA = None 
tempo_inicio_validacao = None 

# Função Auxiliar
def calcular_largura_v(y_atual, y_topo, y_base, w_topo, w_base):
    if y_base == y_topo: return w_base
    fator = (y_atual - y_topo) / (y_base - y_topo)
    return int(w_topo + (w_base - w_topo) * fator)

# ============================================================================
# 3. LOOP PRINCIPAL
# ============================================================================
print(">>> SISTEMA BLINDADO INICIADO <<<")
time.sleep(1)
falar("Sistema Iniciado", prioridade=True)

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (600, 400))
    altura, largura, _ = frame.shape
    centro_x = 300
    centro_y = 200
    
    frame_blur = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    
    mask_amarelo = cv2.inRange(hsv, AMARELO_MIN, AMARELO_MAX)
    mask_buraco = cv2.inRange(hsv, PRETO_MIN, PRETO_MAX)
    mask_vermelho = cv2.inRange(hsv, VERMELHO_MIN, VERMELHO_MAX)

    mensagem_central = ""
    cor_texto = (255, 255, 255)
    
    candidato_perigo = False
    dados_perigo = None      
    modo_desvio_ativo = False
    alvo_amarelo_x = None

    # PASSO 0: MAPEAMENTO
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

    # PASSO 1: DETECÇÃO
    box_x1 = centro_x - (LARGURA_BOX // 2)
    box_x2 = centro_x + (LARGURA_BOX // 2)
    box_y1 = centro_y - (ALTURA_BOX // 2) + 50
    box_y2 = box_y1 + ALTURA_BOX
    
    cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (200, 200, 200), 1)

    # Vermelho
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

    # Preto
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

    # PASSO 2: VALIDAÇÃO
    if candidato_perigo:
        if tempo_inicio_validacao is None:
            tempo_inicio_validacao = time.time()
        
        tempo_decorrido = time.time() - tempo_inicio_validacao
        x, y, w, h, tipo = dados_perigo
        
        if tempo_decorrido >= TEMPO_MINIMO_PERIGO:
            modo_desvio_ativo = True
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.putText(frame, f"{tipo} CONFIRMADO", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (255, 0, 255), 2)
        else:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 165, 255), 2)
            progresso = int((tempo_decorrido / TEMPO_MINIMO_PERIGO) * w)
            cv2.rectangle(frame, (x, y+h+5), (x+progresso, y+h+15), (0, 165, 255), -1)
            cv2.putText(frame, "Validando...", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
    else:
        tempo_inicio_validacao = None

    # PASSO 3: MENSAGEM
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
            mensagem_central = f"{tipo}! PARE AGORA!"
        cor_texto = (0, 0, 255)

    else:
        y_inicio_zona = altura - ALTURA_ZONA_CONTATO
        roi_contato = mask_amarelo[y_inicio_zona:altura, int(centro_x-105):int(centro_x+105)]
        
        if cv2.countNonZero(roi_contato) > 5000:
            ESTA_NA_LINHA = True
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 255, 0), 2)
        else:
            ESTA_NA_LINHA = False
            cv2.rectangle(frame, (centro_x-105, y_inicio_zona), (centro_x+105, altura), (0, 0, 255), 2)

        if ESTA_NA_LINHA != ULTIMO_ESTADO_LINHA:
            if ESTA_NA_LINHA: falar("No caminho", prioridade=True)
            else: falar("Fora do caminho", prioridade=True)
            ULTIMO_ESTADO_LINHA = ESTA_NA_LINHA

        if alvo_amarelo_x is not None:
            cy = alvo_amarelo_y
            limite_leve = calcular_largura_v(cy, 100, 400, W_TOPO_LEVE, W_BASE_LEVE)
            limite_brusco = calcular_largura_v(cy, 100, 400, W_TOPO_BRUSCA, W_BASE_BRUSCA)
            
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
        else:
            if ESTA_NA_LINHA:
                pass 
            else:
                mensagem_central = "Procurando caminho..."
                cor_texto = (0, 0, 255)

    # ---------------------------------------------------------------------
    # 4. LÓGICA DE FALA AJUSTADA
    # ---------------------------------------------------------------------
    agora = time.time()
    deve_falar = False
    
    texto_fala = mensagem_central.replace(">>", "").replace("<<", "").replace("!", "").replace("^", "")
    
    if mensagem_central != "" and mensagem_central != "Procurando caminho...":
        
        # REGRA 1: MUDANÇA -> FALA JÁ
        if texto_fala != ultima_mensagem_falada:
            deve_falar = True
        
        # REGRA 2: REPETIÇÃO
        else:
            # Perigo (Repete a cada 2s)
            if modo_desvio_ativo and (agora - tempo_ultima_fala > 2.0):
                deve_falar = True
            # Navegação (Repete a cada 4s)
            elif not modo_desvio_ativo and (agora - tempo_ultima_fala > 4.0):
                deve_falar = True

    if deve_falar:
        falar(texto_fala, prioridade=modo_desvio_ativo)
        ultima_mensagem_falada = texto_fala
        tempo_ultima_fala = agora

    cv2.rectangle(frame, (0, 0), (600, 60), (0, 0, 0), -1)
    cv2.putText(frame, mensagem_central, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor_texto, 2)
    cv2.imshow("Navegador Audio Blindado", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()