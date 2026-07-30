"""
Ponto de Entrada Principal da Aplicação "Equipe de IA".

Este script orquestra o fluxo de trabalho completo:
1. Carrega as configurações (chaves de API, etc.).
2. Inicializa o modelo de IA generativa.
3. Busca dados de produtos do Bling ERP (ou usa dados simulados).
4. Executa a equipe de IA com um ciclo de revisão:
   - Agente 1: Gera o briefing.
   - Agente 2: Cria o roteiro.
   - Agente 3: Cria as imagens (placeholders).
   - Agente 4: Revisa o conteúdo (roteiro + imagens).
   - Se reprovado, volta para o Agente 2 com feedback.
   - Se aprovado, o Agente Finalizador formata a saída.
5. Salva o resultado em um arquivo Markdown.
6. Envia o resultado para um webhook, se configurado.
"""

import sys
# A biblioteca mais recente 'google-genai' usa 'from google import genai'
# e lê a chave de API automaticamente das variáveis de ambiente.
import google.genai as genai

# Módulos do projeto
from config import CONFIG
from integrations import bling_erp, output_manager
from agents import equipe

# Constante para o número máximo de revisões
MAX_REVISIONS = 3

def run_ai_team_flow():
    """Função principal que executa todo o fluxo da equipe de IA."""
    print("--- INICIANDO PROCESSO DE GERAÇÃO DE CONTEÚDO ---")

    try:
        # 1. INICIALIZAÇÃO DO MODELO
        print(f"1. Inicializando o modelo Gemini: {CONFIG['gemini_model']}")
        # A nova SDK 'google-genai' utiliza um objeto Client.
        # A chave de API é lida automaticamente da variável de ambiente GEMINI_API_KEY.
        try:
            client = genai.Client()
        except Exception as e:
            print(f"Erro ao inicializar o cliente Gemini: {e}")
            sys.exit(1)

        model_name = CONFIG['gemini_model']

        # 2. BUSCA DE PRODUTOS
        print("\n2. Buscando dados de produtos...")
        product_list = bling_erp.get_products_from_bling(CONFIG['bling_api_token'])
        if not product_list:
            print("Erro crítico: Não foi possível obter a lista de produtos. Encerrando.")
            return

        # 3. EXECUÇÃO DOS AGENTES
        print("\n3. Acionando a Equipe de IA...")

        # AGENTE 1
        print("   - [AGENTE 1/5] O Estrategista de Conteúdo está gerando o briefing...")
        briefing_agente_1 = equipe.run_agent_1(product_list, client, model_name)
        if not briefing_agente_1:
            print("   - FALHA: O Agente 1 não conseguiu gerar o briefing. Encerrando.")
            return
        print("   - SUCESSO: Agente 1 concluiu o briefing.")
        
        # AGENTE 2
        print("\n   - [AGENTE 2/5] O Copywriter está criando o rascunho inicial...")
        rascunho_agente_2 = equipe.run_agent_2(briefing_agente_1, client, model_name)
        if not rascunho_agente_2:
            print("   - FALHA: O Agente 2 não conseguiu gerar o rascunho. Encerrando.")
            return
        print("   - SUCESSO: Agente 2 concluiu o roteiro e a legenda.")

        # CICLO DE REVISÃO E APROVAÇÃO
        conteudo_aprovado = None
        feedback_revisor = None

        for i in range(MAX_REVISIONS):
            print(f"\n--- CICLO DE REVISÃO Nº {i + 1} de {MAX_REVISIONS} ---")

            # Se houver feedback, o Agente 2 refaz o trabalho
            if feedback_revisor:
                print("\n   - [AGENTE 2 REVISÃO] O Copywriter está ajustando o rascunho...")
                rascunho_agente_2 = equipe.run_agent_2_revision(
                    briefing=briefing_agente_1,
                    previous_draft=rascunho_agente_2,
                    feedback=feedback_revisor,
                    client=client,
                    model_name=model_name
                )
                if not rascunho_agente_2:
                    print("   - FALHA: O Agente 2 (Revisão) não conseguiu gerar o novo rascunho. Encerrando.")
                    return
                print("   - SUCESSO: Agente 2 concluiu os ajustes.")

            # AGENTE 3
            print("\n   - [AGENTE 3/5] O Criador de Imagens está gerando as imagens...")
            roteiro_com_imagens = equipe.run_agent_3_image_creator(rascunho_agente_2, client)
            if not roteiro_com_imagens:
                print("   - FALHA: O Agente 3 não conseguiu gerar as imagens. Encerrando.")
                return
            
            # AGENTE 4
            print("\n   - [AGENTE 4/5] O Designer Tipográfico está aplicando os textos...")
            roteiro_diagramado = equipe.run_agent_4_typographer(roteiro_com_imagens)
            if not roteiro_diagramado:
                print("   - FALHA: O Agente 4 não conseguiu diagramar as imagens. Encerrando.")
                return
            
            # AGENTE 5
            print("\n   - [AGENTE 5/5] O Revisor Chefe está analisando o material...")
            resultado_revisao = equipe.run_agent_5_reviewer(roteiro_diagramado, client, model_name)
            if not resultado_revisao:
                print("   - FALHA: O Agente 5 não conseguiu concluir a revisão. Encerrando.")
                return

            if resultado_revisao.get("status") == "APROVADO":
                print("   - SUCESSO: Conteúdo APROVADO pelo Revisor Chefe!")
                conteudo_aprovado = roteiro_diagramado
                break
            else:
                feedback_revisor = resultado_revisao.get("feedback")
                print(f"   - REPROVADO: O revisor solicitou ajustes.")
                print(f"   - Feedback: {feedback_revisor}")
        
        # 4. FINALIZAÇÃO
        if not conteudo_aprovado:
            print("\n--- PROCESSO ENCERRADO ---")
            print(f"O conteúdo não foi aprovado após {MAX_REVISIONS} tentativas.")
            return

        print("\n4. Finalizando e salvando o conteúdo aprovado...")
        conteudo_final_markdown = equipe.run_finalizer(conteudo_aprovado, client, model_name)
        if not conteudo_final_markdown:
            print("   - FALHA: O Agente Finalizador não conseguiu gerar o Markdown. Encerrando.")
            return

        output_manager.save_to_markdown(conteudo_final_markdown)
        output_manager.send_to_webhook(conteudo_final_markdown, CONFIG['webhook_url'])

        print("\n--- CONTEÚDO FINAL GERADO ---")
        print(conteudo_final_markdown)
        print("--- PROCESSO CONCLUÍDO COM SUCESSO ---")

    except Exception as e:
        print(f"\n--- OCORREU UM ERRO CRÍTICO NO FLUXO PRINCIPAL ---", file=sys.stderr)
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_ai_team_flow()
