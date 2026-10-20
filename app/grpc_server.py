import grpc
from app.proto import ia_service_pb2_grpc
from app.agent.ia_servicer import IAServiceServicer


async def serve_grpc():
    server = grpc.aio.server(options=[
        ("grpc.keepalive_time_ms", 30000),
        ("grpc.keepalive_timeout_ms", 10000),
        ("grpc.keepalive_permit_without_calls", 1),
        ("grpc.http2.min_ping_interval_without_data_ms", 10000),
        ("grpc.http2.max_pings_without_data", 0),
    ])
    ia_service_pb2_grpc.add_IAServiceServicer_to_server(IAServiceServicer(), server)

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)

    print(f"📡 gRPC Server escutando em {listen_addr}")
    await server.start()
    await server.wait_for_termination()