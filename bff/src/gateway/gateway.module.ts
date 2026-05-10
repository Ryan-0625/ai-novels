import { Module } from '@nestjs/common';
import { EventsGateway } from './gateway';

@Module({
  providers: [EventsGateway],
  exports: [EventsGateway],
})
export class GatewayModule {}
