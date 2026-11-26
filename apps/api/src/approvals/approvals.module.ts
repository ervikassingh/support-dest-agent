import { Module } from '@nestjs/common';
import { AgentClientService } from '../agent-client.service';
import { ApprovalsController } from './approvals.controller';
import { ApprovalsService } from './approvals.service';

@Module({
  controllers: [ApprovalsController],
  providers: [ApprovalsService, AgentClientService],
})
export class ApprovalsModule {}
