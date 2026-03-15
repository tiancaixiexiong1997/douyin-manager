import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { downloadApi } from '../../api/client';
import { Download, Search, DouyinIcon } from '../../components/Icons';
import { Zap, Video, Smartphone } from 'lucide-react';
import './VideoDownloader.css';

export default function VideoDownloader() {
  const [url, setUrl] = useState('');

  const parseMutation = useMutation({
    mutationFn: downloadApi.parse,
  });
  const downloadMutation = useMutation({
    mutationFn: (params: { url: string; filename: string; video_id?: string }) => downloadApi.proxyDownload(params),
  });

  const handleParse = () => {
    if (!url.trim()) return;
    parseMutation.mutate(url.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleParse();
    }
  };

  const handleDownload = async () => {
    if (!parseMutation.data?.video_url) return;
    const filename = `${(parseMutation.data.title || parseMutation.data.video_id || 'video').slice(0, 50)}.mp4`;
    try {
      const blob = await downloadMutation.mutateAsync({
        url: parseMutation.data.video_url,
        filename,
        video_id: parseMutation.data.video_id,
      });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch {
      // 统一错误信息由 mutation.isError 渲染
    }
  };

  return (
    <div className="downloader-container">


      <div className="card downloader-hero animate-fade-in">
        <div className="hero-text">
          <div className="downloader-pill"><Zap size={13} /> Download Engine</div>
          <h2>视频去水印极速解析</h2>
          <p>突破平台保存限制，粘贴视频分享链接，一键提取最高清无水印原文件，直接保存到本地供创作参考。</p>
        </div>
        
        <div className="hero-input-wrap">
          <div className="hero-input-icon">
            <DouyinIcon size={18} />
          </div>
          <input
            type="text"
            className="form-input"
            placeholder="请粘贴抖音/TikTok 视频分享链接（例如：https://v.douyin.com/xxxx/）"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button 
            className="btn btn-primary" 
            onClick={handleParse}
            disabled={!url.trim() || parseMutation.isPending}
          >
            {parseMutation.isPending ? (
              <><div className="spinner" style={{ width: 16, height: 16, borderTopColor: 'currentColor' }} /> 解析中...</>
            ) : (
              <><Search size={16} /> 立即解析</>
            )}
          </button>
        </div>
        {parseMutation.isError && (
          <div className="error-tip" style={{ marginTop: 8 }}>
            {(parseMutation.error as Error).message}
          </div>
        )}
      </div>

      {!parseMutation.isSuccess && !parseMutation.isPending && (
        <div className="features-grid animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="feature-card">
            <div className="feature-icon-wrap"><Video size={20} /></div>
            <h3>无损最高画质</h3>
            <p>直接解析原始视频 MP4 地址，绕过客户端二次压缩，获取原作者上传级画质</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon-wrap"><Zap size={20} /></div>
            <h3>毫无痕迹</h3>
            <p>彻底去除原视频四周悬浮的平台 Watermark 水印与末尾的品牌片尾贴片</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon-wrap"><Smartphone size={20} /></div>
            <h3>全移动端兼容</h3>
            <p>支持识别包括抖音短口令、带图文长内容在内的所有常用分享格式</p>
          </div>
        </div>
      )}

      {parseMutation.isSuccess && parseMutation.data && (
        <div className="result-section">
          <div className="video-preview">
            <div className="video-cover-wrap">
              {parseMutation.data.cover_url ? (
                <img src={parseMutation.data.cover_url} alt="视频封面" />
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#eee', color: '#999' }}>无封面</div>
              )}
            </div>
            <div className="video-info">
              <div className="video-title">
                {parseMutation.data.title || '（未命名视频）'}
              </div>
              
              <div className="download-actions" style={{ marginTop: 'auto' }}>
                {parseMutation.data.video_url ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ textDecoration: 'none', padding: '12px 24px', fontSize: 15 }}
                    onClick={handleDownload}
                    disabled={downloadMutation.isPending}
                  >
                    <Download size={18} />
                    {downloadMutation.isPending ? '下载中...' : '下载无水印原片'}
                  </button>
                ) : (
                  <div className="error-tip">未解析到无水印直链</div>
                )}
                {downloadMutation.isError && (
                  <div className="error-tip" style={{ marginTop: 8 }}>
                    {(downloadMutation.error as Error).message}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
