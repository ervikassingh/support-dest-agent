import { Body, Controller, Param, Post } from '@nestjs/common';
import { ApprovalsService } from './approvals.service';

type ApprovalBody = {
  decision: 'approve' | 'edit' | 'reject';
  amount?: number;
  note?: string;
};

@Controller('approvals')
export class ApprovalsController {
  constructor(private readonly approvalsService: ApprovalsService) {}

  @Post(':threadId')
  decide(@Param('threadId') threadId: string, @Body() body: ApprovalBody) {
    return this.approvalsService.decide(threadId, body);
  }
}
