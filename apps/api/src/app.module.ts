import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ApprovalsModule } from './approvals/approvals.module';
import { ChatModule } from './chat/chat.module';
import { DocumentsModule } from './documents/documents.module';
import { EvalsModule } from './evals/evals.module';
import { HealthController } from './health.controller';
import { AgentClientService } from './agent-client.service';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env', '../../.env'],
    }),
    ChatModule,
    ApprovalsModule,
    DocumentsModule,
    EvalsModule,
  ],
  controllers: [HealthController],
  providers: [AgentClientService],
  exports: [AgentClientService],
})
export class AppModule {}
