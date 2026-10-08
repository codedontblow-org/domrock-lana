import asyncio
from app.proto import ia_service_pb2, ia_service_pb2_grpc
# import do seu agente/grafo aqui

class IAServiceServicer(ia_service_pb2_grpc.IAServiceServicer):
    
    async def InvokeAgent(self, request, context):
        # Exemplo chamando a execução síncrona do agente via thread separada
        # resultado = await asyncio.to_thread(executar_agente, request.prompt)
        
        response = ia_service_pb2.InvokeResponse(
            resposta="Resposta processada pelo agente gRPC"
        )
        return response