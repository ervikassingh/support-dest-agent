import { Body, Controller, Get, HttpCode, Param, Post, Query } from '@nestjs/common';
import { EvalsService, StartRunBody } from './evals.service';

@Controller('evals')
export class EvalsController {
  constructor(private readonly evals: EvalsService) {}

  @Get(':suite/runs')
  list(@Param('suite') suite: string, @Query('limit') limit?: string) {
    return this.evals.list(this.evals.parseSuite(suite), limit);
  }

  @Get(':suite/runs/:id')
  get(@Param('suite') suite: string, @Param('id') id: string) {
    return this.evals.get(this.evals.parseSuite(suite), id);
  }

  @Post(':suite/runs')
  @HttpCode(202)
  start(@Param('suite') suite: string, @Body() body: StartRunBody) {
    return this.evals.start(this.evals.parseSuite(suite), body ?? {});
  }
}
