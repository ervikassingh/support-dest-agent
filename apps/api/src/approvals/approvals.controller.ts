import { Body, Controller, Get, Param, Post, Query } from '@nestjs/common';
import { ApprovalsService } from './approvals.service';

type ApprovalBody = {
  decision: 'approve' | 'edit' | 'reject';
  amount?: number;
  note?: string;
};

@Controller('approvals')
export class ApprovalsController {
  constructor(private readonly approvalsService: ApprovalsService) {}

  @Get()
  list(@Query('state') state?: string, @Query('limit') limit?: string) {
    return this.approvalsService.list(state, limit);
  }

  @Post(':threadId')
  decide(@Param('threadId') threadId: string, @Body() body: ApprovalBody) {
    return this.approvalsService.decide(threadId, body);
  }
}
