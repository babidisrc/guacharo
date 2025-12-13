import cv2
import numpy as np
import os

# ============================================================================
# 1. CONFIGURAÇÃO
# ============================================================================
# Verifique se o vídeo tem o obstáculo vermelho ou use 0 para Webcam
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\CaminhoAmareloObstaculo-2.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO] Vídeo não encontrado")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

# ============================================================================
# 2. CALIBRAGEM (Baseada na imagem image_e599c3.png)
# ============================================================================
vermelho_min = np.array([0, 85, 85])
vermelho_max = np.array([4, 255, 255])

# Filtros Geométricos
ALTURA_IGNORE_PES = 60  # Ignora os últimos 60px (pés)
AREA_MINIMA = 1000      # Ignora ruídos pequenos

print(">>> DETECTOR DE OBSTÁCULO VERMELHO <<<")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (600, 400))
    altura, largura, _ = frame.shape
    centro_tela = 300
    
    # Tratamento
    frame_blur = cv2.GaussianBlur(frame, (5, 5), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    
    # Cria a Máscara Vermelha
    mask_vermelho = cv2.inRange(hsv, vermelho_min, vermelho_max)
    
    # --- FILTRO: CORTE DOS PÉS ---
    # Garante que não detecte sapatos vermelhos
    mask_vermelho[altura-ALTURA_IGNORE_PES:altura, :] = 0
    cv2.line(frame, (0, altura-ALTURA_IGNORE_PES), (largura, altura-ALTURA_IGNORE_PES), (0, 0, 255), 1)

    # Encontra contornos
    contornos, _ = cv2.findContours(mask_vermelho, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    mensagem = "CAMINHO LIVRE"
    cor_texto = (0, 255, 0)

    for cnt in contornos:
        area = cv2.contourArea(cnt)
        
        if area > AREA_MINIMA:
            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            
            # Desenha o obstáculo
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.putText(frame, "OBSTACULO", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Lógica de aviso simples
            mensagem = "OBSTACULO DETECTADO!"
            cor_texto = (0, 0, 255)
            
            # Verifica se está no centro
            if cx < centro_tela - 100:
                cv2.putText(frame, "<< esta na esquerda", (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            elif cx > centro_tela + 100:
                cv2.putText(frame, "esta na direita >>", (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            else:
                cv2.putText(frame, "!! A FRENTE !!", (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Interface
    cv2.putText(frame, mensagem, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor_texto, 2)
    
    # Mostra a máscara para você conferir se está pegando certo
    cv2.imshow("Mascara Vermelha", mask_vermelho)
    cv2.imshow("Detector de Obstaculo", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()