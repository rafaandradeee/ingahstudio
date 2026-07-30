import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

print("1. Lendo o arquivo .env...")
load_dotenv() # Obriga o Python a abrir o seu .env

# Busca a chave seja lá qual for o nome que você usou!
minha_chave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not minha_chave:
    print("❌ ERRO: Não achei a chave! Verifique se ela está no .env como GEMINI_API_KEY ou GOOGLE_API_KEY")
    exit()

print("2. Chave encontrada! Chamando o modelo gemini-3.1-flash-image...")

try:
    # Passamos a chave explicitamente para o cliente!
    client = genai.Client(api_key=minha_chave)
    
    response = client.models.generate_content(
        model='models/gemini-3.1-flash-image',
        contents='Um logo de um urso bebendo café, estilo neon, fundo escuro',
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"] 
        )
    )
    
    print("3. Resposta recebida! Procurando a imagem...")
    imagem_bytes = None
    
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                imagem_bytes = part.inline_data.data
                break
                
    if imagem_bytes:
        with open("teste_isolado.png", "wb") as f:
            f.write(imagem_bytes)
        print("✅ SUCESSO ABSOLUTO! A imagem 'teste_isolado.png' foi criada na sua pasta!")
    else:
        print("❌ O Google não mandou os pixels. Resposta: " + response.text)

except Exception as e:
    print(f"\n❌ ERRO DA API: {str(e)}")