import { Controller, Get, Param, Post, Body, Inject } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

@Controller('tasks')
export class TasksController {
  constructor(@Inject(HttpService) private readonly http: HttpService) {}

  @Get()
  async listTasks() {
    const { data } = await firstValueFrom(this.http.get('/tasks'));
    return data;
  }

  @Get(':id')
  async getTask(@Param('id') id: string) {
    const { data } = await firstValueFrom(this.http.get(`/tasks/${id}`));
    return data;
  }

  @Post(':id/action')
  async actionTask(@Param('id') id: string, @Body() body: { action: string }) {
    const { data } = await firstValueFrom(this.http.post(`/tasks/${id}/action`, body));
    return data;
  }

  @Get('workflows/definitions')
  async listWorkflows() {
    const { data } = await firstValueFrom(this.http.get('/tasks/workflows/definitions'));
    return data;
  }
}
