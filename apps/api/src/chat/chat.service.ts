import { BadRequestException, Injectable } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';

@Injectable()
export class ChatService {
  constructor(private readonly agent: AgentClientService) {}

  async handleChat(body: { message?: string; threadId?: string | null }) {
    if (!body.message?.trim()) {
      throw new BadRequestException('message is required');
    }

    // Auth/session stubs can wrap this later. Nest proxies to the agent only —
    // it does not host MCP or implement RAG.
    return this.agent.chat({
      message: body.message.trim(),
      threadId: body.threadId,
    });
  }
}
