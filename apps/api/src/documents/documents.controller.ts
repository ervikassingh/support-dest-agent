import {
  BadRequestException,
  Body,
  CallHandler,
  Controller,
  ExecutionContext,
  Get,
  Injectable,
  NestInterceptor,
  Param,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { Observable } from 'rxjs';
import { DocumentsService } from './documents.service';

function OptionalFileInterceptor() {
  const Mixin = FileInterceptor('file', { limits: { fileSize: 20 * 1024 * 1024 } });

  @Injectable()
  class Interceptor extends Mixin implements NestInterceptor {
    intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> | Promise<Observable<unknown>> {
      const request = context.switchToHttp().getRequest<{ headers: Record<string, string> }>();
      const type = request.headers['content-type'] ?? '';
      if (!type.includes('multipart/form-data')) {
        return next.handle();
      }
      return super.intercept(context, next);
    }
  }

  return Interceptor;
}

@Controller('documents')
export class DocumentsController {
  constructor(private readonly documents: DocumentsService) {}

  @Post()
  @UseInterceptors(OptionalFileInterceptor())
  create(
    @UploadedFile() file: Express.Multer.File | undefined,
    @Body() body: { url?: string },
  ) {
    const url = body?.url?.trim();
    if (!file && !url) {
      throw new BadRequestException('Provide a file or a url');
    }
    if (file && url) {
      throw new BadRequestException('Provide a file or a url, not both');
    }
    return file ? this.documents.uploadFile(file) : this.documents.uploadUrl(url!);
  }

  @Get()
  list() {
    return this.documents.list();
  }

  @Get(':id')
  get(@Param('id') id: string) {
    return this.documents.get(id);
  }
}
