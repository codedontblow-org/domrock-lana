import asyncio
import time
import traceback

import grpc

from app.agent.router import _eh_limite_de_cota, MENSAGEM_COTA
from app.agent.service import lana_invoke
from app.proto import ia_service_pb2, ia_service_pb2_grpc


class IAServiceServicer(ia_service_pb2_grpc.IAServiceServicer):

    async def InvokeAgent(self, request, context):
        print(f"Recebido | chat={request.chat_id} | prompt={request.prompt!r}", flush=True)
        inicio = time.perf_counter()
        try:
            resultado = await asyncio.wait_for(
                asyncio.to_thread(lana_invoke, request.chat_id, request.prompt, None),
                timeout=100,
            )
            print(f"Respondido em {time.perf_counter() - inicio:.1f}s", flush=True)
            return ia_service_pb2.InvokeResponse(resposta=resultado["response"])

        except asyncio.TimeoutError:
            print(f"Lana passou de 100s (chat={request.chat_id})", flush=True)
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "A Lana demorou demais para responder.")
        except Exception as e:
            traceback.print_exc()
            if _eh_limite_de_cota(e):
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, MENSAGEM_COTA)
            await context.abort(grpc.StatusCode.INTERNAL, f"Erro no agente: {e}")