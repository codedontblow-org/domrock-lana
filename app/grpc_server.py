import grpc
from app.proto import ia_service_pb2_grpc
from app.agent.ia_servicer import IAServiceServicer

async def serve_grpc():
    server = grpc.aio.server()
    ia_service_pb2_grpc.add_IAServiceServicer_to_server(IAServiceServicer(), server)
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    print(f"📡 gRPC Server escutando em {listen_addr}")
    await server.start()
    await server.wait_for_termination()