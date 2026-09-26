import asyncio
import grpc
from app.proto import ia_service_pb2, ia_service_pb2_grpc

# Importa a sua função de execução do agente do LangGraph
from app.agent.service import lana_invoke


class IAServiceServicer(ia_service_pb2_grpc.IAServiceServicer):
    async def GerarResposta(self, request, context):
        usuario_id = request.usuario_id
        prompt = request.prompt
        contexto = request.contexto

        print(f"Prompt recebido do usuário {usuario_id}: {prompt}")

        try:
            # Usamos o ID do usuário (ou sessão) como o thread_id do LangGraph
            thread_id = str(usuario_id)

            # Executa o lana_invoke em uma thread separada para não travar o loop async
            resultado = await asyncio.to_thread(lana_invoke, thread_id, prompt)

            # Captura a resposta gerada pelo agente
            texto_resposta = resultado.get("response", "Sem resposta gerada.")

            print(f"Resposta gerada com sucesso!")

        except Exception as e:
            print(f"Erro ao processar o agente LangGraph: {e}")
            texto_resposta = "Desculpe, ocorreu um erro ao processar sua solicitação com a Lana."

        return ia_service_pb2.PromptResponse(
            resposta=texto_resposta,
            tokens_utilizados=150
        )

    gerarResposta = GerarResposta

async def serve():
    server = grpc.aio.server()

    # Registra o serviço gRPC
    ia_service_pb2_grpc.add_IAServiceServicer_to_server(
        IAServiceServicer(), server
    )

    server.add_insecure_port("0.0.0.0:50051")
    print("Servidor gRPC IAService rodando na porta 50051 com Lana conectada!")

    await server.start()
    await server.wait_for_termination()