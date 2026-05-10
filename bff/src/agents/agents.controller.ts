import { Controller, Get, Param, Patch, Body, Inject } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

@Controller('agents')
export class AgentsController {
  constructor(@Inject(HttpService) private readonly http: HttpService) {}

  @Get()
  async listAgents() {
    const { data } = await firstValueFrom(this.http.get('/agents'));
    return data;
  }

  @Get(':name')
  async getAgent(@Param('name') name: string) {
    const { data } = await firstValueFrom(this.http.get(`/agents/${name}`));
    return data;
  }

  @Get(':name/metrics')
  async getMetrics(@Param('name') name: string) {
    const { data } = await firstValueFrom(this.http.get(`/agents/${name}/metrics`));
    return data;
  }

  @Patch(':name/config')
  async updateConfig(@Param('name') name: string, @Body() body: any) {
    const { data } = await firstValueFrom(this.http.patch(`/agents/${name}/config`, body));
    return data;
  }
}
