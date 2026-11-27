import { BadRequestException, Injectable } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';

@Injectable()
export class ApprovalsService {
  constructor(private readonly agent: AgentClientService) {}

  async decide(
    threadId: string,
    body: { decision?: 'approve' | 'edit' | 'reject'; amount?: number; note?: string },
  ) {
    if (!threadId?.trim()) {
      throw new BadRequestException('threadId is required');
    }
    if (!body.decision || !['approve', 'edit', 'reject'].includes(body.decision)) {
      throw new BadRequestException('decision must be approve | edit | reject');
    }
    if (body.decision === 'edit' && (body.amount === undefined || Number.isNaN(body.amount))) {
      throw new BadRequestException('amount is required when decision is edit');
    }

    return this.agent.resume(threadId.trim(), {
      decision: body.decision,
      amount: body.amount,
      note: body.note,
    });
  }
}
