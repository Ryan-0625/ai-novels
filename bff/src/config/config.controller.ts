import { Controller, Get, Param, Post, Inject } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

@Controller('config')
export class ConfigController {
  constructor(@Inject(HttpService) private readonly http: HttpService) {}

  @Get()
  async getFullConfig() {
    const { data } = await firstValueFrom(this.http.get('/config'));
    return data;
  }

  @Get(':keyPath')
  async getItem(@Param('keyPath') keyPath: string) {
    const { data } = await firstValueFrom(this.http.get(`/config/${keyPath}`));
    return data;
  }

  @Post('reload')
  async reloadConfig() {
    const { data } = await firstValueFrom(this.http.post('/config/reload'));
    return data;
  }

  @Get('novel/presets')
  async listPresets() {
    const { data } = await firstValueFrom(this.http.get('/config/novel/presets'));
    return data;
  }

  @Get('novel/presets/:name')
  async getPreset(@Param('name') name: string) {
    const { data } = await firstValueFrom(this.http.get(`/config/novel/presets/${name}`));
    return data;
  }
}
