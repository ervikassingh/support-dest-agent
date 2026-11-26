import { Controller, Get } from '@nestjs/common';

@Controller('health')
export class HealthController {
  @Get()
  health() {
    return {
      status: 'ok',
      service: 'api',
      agentUrl: process.env.AGENT_URL ?? 'http://localhost:8000',
    };
  }
}
