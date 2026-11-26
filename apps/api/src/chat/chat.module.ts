import { Module } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';

@Module({
  controllers: [ChatController],
  providers: [ChatService, AgentClientService],
})
export class ChatModule {}
