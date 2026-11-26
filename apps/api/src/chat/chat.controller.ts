import { Body, Controller, Post } from '@nestjs/common';
import { ChatService } from './chat.service';

type ChatBody = {
  message: string;
  threadId?: string | null;
};

@Controller('chat')
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  @Post()
  chat(@Body() body: ChatBody) {
    return this.chatService.handleChat(body);
  }
}
