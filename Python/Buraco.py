import cv2
import numpy as np
import os

def nada(x): pass

# ============================================================================
# 1. CONFIGURAÇÃO
# ============================================================================
CAMINHO_VIDEO = r"C:\Users\Pedro\Desktop\Visão Computacional\Vídeos-2\CaminhoAmareloBuraco-1.mp4"

if not os.path.exists(CAMINHO_VIDEO):
    print("[ERRO] Vídeo não encontrado!")
    exit()

cap = cv2.VideoCapture(CAMINHO_VIDEO)

# ============================================================================
# 2. JANELA DE CONTROLES
# ============================================================================
cv2.namedWindow("Ajuste Geometrico")
cv2.resizeWindow("Ajuste Geometrico", 600, 200)

# Barra 1: Altura da Linha (Ignorar Pés)
# Vai de 0 (base) até 200 (meio da tela)
cv2.createTrackbar("Corte Pes (Y)", "Ajuste Geometrico", 60, 200, nada)

# Barra 2: Circularidade Mínima
# Vai de 10 (0.1) até 90 (0.9). Dividiremos por 100 no código.
# Quanto maior, mais "redondo" o objeto precisa ser para ser considerado buraco.
cv2.createTrackbar("Circularidade", "Ajuste Geometrico", 35, 100, nada)

# ============================================================================
# 3. COR PRETA (JÁ CONFIGURADA)
# ============================================================================
# Configuração baseada na sua imagem 'image_9928a7.png'
preto_min = np.array([0, 29, 28])
preto_max = np.array([179, 102, 100])

print(">>> CALIBRADOR DE FORMA E POSIÇÃO <<<")
print("VERDE = Buraco Confirmado")
print("VERMELHO = Ignorado (Tênis, Sombra Irregular ou Área Proibida)")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (600, 400))
    altura_tela, largura_tela, _ = frame.shape
    
    # Processamento visual
    frame_blur = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2HSV)
    mask_buraco = cv2.inRange(hsv, preto_min, preto_max)

    # -----------------------------------------------------------
    # LER OS AJUSTES
    # -----------------------------------------------------------
    corte_pes = cv2.getTrackbarPos("Corte Pes (Y)", "Ajuste Geometrico")
    min_circularidade = cv2.getTrackbarPos("Circularidade", "Ajuste Geometrico") / 100.0

    # Desenha a linha amarela de corte na tela
    linha_y = altura_tela - corte_pes
    cv2.line(frame, (0, linha_y), (largura_tela, linha_y), (0, 255, 255), 2)
    cv2.putText(frame, "AREA IGNORADA (PES)", (10, altura_tela - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # -----------------------------------------------------------
    # ANÁLISE DOS OBJETOS
    # -----------------------------------------------------------
    contornos, _ = cv2.findContours(mask_buraco, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contornos:
        area = cv2.contourArea(cnt)
        
        # Filtro de tamanho (ignora sujeira pequena)
        if area > 1000:
            perimetro = cv2.arcLength(cnt, True)
            if perimetro == 0: continue
            
            # Cálculo matemático da forma (1.0 = Círculo perfeito)
            circularidade = 4 * np.pi * (area / (perimetro * perimetro))
            
            # Verifica posição
            x, y, w, h = cv2.boundingRect(cnt)
            base_objeto = y + h
            
            # --- TESTES DE VALIDAÇÃO ---
            falhou_posicao = base_objeto > linha_y # Tocou na linha amarela?
            falhou_forma = circularidade < min_circularidade # É muito torto?

            # DECISÃO E DESENHO
            if not falhou_posicao and not falhou_forma:
                # PASSOU EM TUDO -> É UM BURACO (VERDE)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"BURACO OK ({circularidade:.2f})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                # FALHOU -> É LIXO/TÊNIS (VERMELHO)
                cv2.drawContours(frame, [cnt], -1, (0, 0, 255), 1)
                
                motivo = ""
                if falhou_posicao: motivo = "PE DETECTADO"
                elif falhou_forma: motivo = f"FORMA ({circularidade:.2f})"
                
                cv2.putText(frame, motivo, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    cv2.imshow("Calibrador Geometrico", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        print("\n" + "="*40)
        print("--- VALORES PARA O CÓDIGO FINAL ---")
        print(f"ALTURA_IGNORE_PES = {corte_pes}")
        print(f"CIRCULARIDADE_MIN = {min_circularidade}")
        print("="*40 + "\n")
        break

cap.release()
cv2.destroyAllWindows()