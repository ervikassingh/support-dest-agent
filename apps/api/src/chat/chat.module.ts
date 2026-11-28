import { Module } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import { ThreadsController } from './threads.controller';

@Module({
  controllers: [ChatController, ThreadsController],
  providers: [ChatService, AgentClientService],
})
export class ChatModule {}
