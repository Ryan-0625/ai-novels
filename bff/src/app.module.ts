import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { HttpModule } from '@nestjs/axios';
import { AgentsController } from './agents/agents.controller';
import { TasksController } from './tasks/tasks.controller';
import { ConfigController } from './config/config.controller';
import { GatewayModule } from './gateway/gateway.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    HttpModule.register({
      baseURL: process.env.AI_ENGINE_URL || 'http://localhost:8004/api/v2',
      timeout: 30000,
    }),
    GatewayModule,
  ],
  controllers: [AgentsController, TasksController, ConfigController],
})
export class AppModule {}
