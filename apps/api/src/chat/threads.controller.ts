import { Controller, Get, Param, Query } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';

@Controller('threads')
export class ThreadsController {
  constructor(private readonly agent: AgentClientService) {}

  @Get()
  list(@Query('limit') limit?: string) {
    const qs = limit ? `?limit=${encodeURIComponent(limit)}` : '';
    return this.agent.getJson(`/threads${qs}`);
  }

  @Get(':threadId')
  get(@Param('threadId') threadId: string) {
    return this.agent.getJson(`/threads/${encodeURIComponent(threadId)}`);
  }
}
