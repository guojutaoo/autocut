[INFO] src.tts.tts_edge: TTS chunk types seen: {'audio', 'SentenceBoundary'}
[INFO] src.tts.tts_edge: TTS synthesis completed: outputs/autocut_project/narrations/narration_00.wav, boundaries collected: 5
[INFO] src.tts.tts_edge: Generated TTS audio at outputs/autocut_project/narrations/narration_00.wav
[INFO] src.tts.tts_edge: Generated TTS boundaries at outputs/autocut_project/narrations/narration_00.boundaries.json
[INFO] xhs_autocut: Narration 00: audio=outputs/autocut_project/narrations/narration_00.wav, dur=46.420s -> freeze=46.520s
[DEBUG] asyncio: Using selector: KqueueSelector
[INFO] src.tts.tts_edge: TTS chunk types seen: {'audio', 'SentenceBoundary'}
[INFO] src.tts.tts_edge: TTS synthesis completed: outputs/autocut_project/narrations/narration_01.wav, boundaries collected: 4
[INFO] src.tts.tts_edge: Generated TTS audio at outputs/autocut_project/narrations/narration_01.wav
[INFO] src.tts.tts_edge: Generated TTS boundaries at outputs/autocut_project/narrations/narration_01.boundaries.json
[INFO] xhs_autocut: Narration 01: audio=outputs/autocut_project/narrations/narration_01.wav, dur=45.600s -> freeze=45.700s
[INFO] xhs_autocut: Composing highlight video from plan...
[INFO] src.freeze_effects.engine: FreezeEffectEngine initialized with white_flash=True, zoom_in=True, stinger=True, zoompan=True
[INFO] src.render.ffmpeg_compose: Freeze effect enabled: weibo_pop
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -ss 243.760 -accurate_seek -i /Users/bytedance/Downloads/01.mp4 -t 5.060 -vf scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black -r 30 -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0000_pre.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0000_pre.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0(und): Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 aac
frame=  113 fps=0.0 q=24.0 size=    1792KiB time=N/A bitrate=N/A speed=N/A    
[out#0/mp4 @ 0x13a704440] video:2617KiB audio:80KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.254449%
frame=  152 fps=0.0 q=-1.0 Lsize=    2703KiB time=00:00:05.00 bitrate=4429.3kbits/s speed= 8.6x    
[libx264 @ 0x13a7052e0] frame I:2     Avg QP: 7.61  size:106960
[libx264 @ 0x13a7052e0] frame P:38    Avg QP:10.68  size: 38941
[libx264 @ 0x13a7052e0] frame B:112   Avg QP:16.27  size:  8795
[libx264 @ 0x13a7052e0] consecutive B-frames:  1.3%  0.0%  3.9% 94.7%
[libx264 @ 0x13a7052e0] mb I  I16..4: 68.6% 23.3%  8.1%
[libx264 @ 0x13a7052e0] mb P  I16..4:  0.2%  1.6%  0.2%  P16..4: 12.0% 12.2%  6.3%  0.0%  0.0%    skip:67.7%
[libx264 @ 0x13a7052e0] mb B  I16..4:  0.3%  1.5%  0.1%  B16..8:  7.4%  4.9%  0.3%  direct: 7.4%  skip:78.2%  L0:39.1% L1:42.1% BI:18.7%
[libx264 @ 0x13a7052e0] 8x8 transform intra:57.6% inter:53.9%
[libx264 @ 0x13a7052e0] coded y,uvDC,uvAC intra: 60.4% 69.1% 53.6% inter: 12.2% 15.2% 2.6%
[libx264 @ 0x13a7052e0] i16 v,h,dc,p: 84%  6%  7%  4%
[libx264 @ 0x13a7052e0] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 28% 11% 21%  3%  8%  9%  6%  7%  6%
[libx264 @ 0x13a7052e0] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 28% 15% 13%  5% 11% 10%  7%  7%  5%
[libx264 @ 0x13a7052e0] i8c dc,h,v,p: 65% 13% 17%  5%
[libx264 @ 0x13a7052e0] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x13a7052e0] ref P L0: 54.8% 45.2%
[libx264 @ 0x13a7052e0] ref B L0: 74.0% 26.0%
[libx264 @ 0x13a7052e0] ref B L1: 93.8%  6.2%
[libx264 @ 0x13a7052e0] kb/s:4229.64
[aac @ 0x13b08a920] Qavg: 713.479
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 46.720 -c:a pcm_s16le outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
ffmpeg version 7.1 Copyright (c) 2000-2024 the FFmpeg developers
  built with Apple clang version 13.1.6 (clang-1316.0.21.2.5)
  configuration: --prefix=/Volumes/tempdisk/sw --extra-cflags=-fno-stack-check --arch=arm64 --cc=/usr/bin/clang --enable-gpl --enable-libvmaf --enable-libopenjpeg --enable-libopus --enable-libmp3lame --enable-libx264 --enable-libx265 --enable-libvpx --enable-libwebp --enable-libass --enable-libfreetype --enable-fontconfig --enable-libtheora --enable-libvorbis --enable-libsnappy --enable-libaom --enable-libvidstab --enable-libzimg --enable-libsvtav1 --enable-libharfbuzz --enable-libkvazaar --pkg-config-flags=--static --enable-ffplay --enable-postproc --enable-neon --enable-runtime-cpudetect --disable-indev=qtkit --disable-indev=x11grab_xcb
  libavutil      59. 39.100 / 59. 39.100
  libavcodec     61. 19.100 / 61. 19.100
  libavformat    61.  7.100 / 61.  7.100
  libavdevice    61.  3.100 / 61.  3.100
  libavfilter    10.  4.100 / 10.  4.100
  libswscale      8.  3.100 /  8.  3.100
  libswresample   5.  3.100 /  5.  3.100
  libpostproc    58.  3.100 / 58.  3.100
Input #0, lavfi, from 'anullsrc=r=44100:cl=stereo':
  Duration: N/A, start: 0.000000, bitrate: 705 kb/s
  Stream #0:0: Audio: pcm_u8, 44100 Hz, stereo, u8, 705 kb/s
Stream mapping:
  Stream #0:0 -> #0:0 (pcm_u8 (native) -> pcm_s16le (native))
Press [q] to stop, [?] for help
Output #0, wav, to 'outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav':
  Metadata:
    ISFT            : Lavf61.7.100
  Stream #0:0: Audio: pcm_s16le ([1][0][0][0] / 0x0001), 44100 Hz, stereo, s16, 1411 kb/s
      Metadata:
        encoder         : Lavc61.19.100 pcm_s16le
[out#0/wav @ 0x156616870] video:0KiB audio:8048KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.000946%
size=    8048KiB time=00:00:46.72 bitrate=1411.2kbits/s speed=4.28e+03x
[INFO] src.render.ffmpeg_compose: Building freeze segment seg_0000: impl=tpad, anchor=248.820s, dur=46.720s
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -ss 248.820 -accurate_seek -i /Users/bytedance/Downloads/01.mp4 -i outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav -filter_complex [0:v]scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black,trim=duration=0.033333,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=46.720[vout] -map [vout] -map 1:a -t 46.720 -r 30 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
Input #1, wav, from 'outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav':
  Metadata:
    encoder         : Lavf61.7.100
  Duration: 00:00:46.72, bitrate: 1411 kb/s
  Stream #1:0: Audio: pcm_s16le ([1][0][0][0] / 0x0001), 44100 Hz, stereo, s16, 1411 kb/s
Stream mapping:
  Stream #0:0 (h264) -> scale:default
  tpad:default -> Stream #0:0 (libx264)
  Stream #1:0 -> #0:1 (pcm_s16le (native) -> aac (native))
Press [q] to stop, [?] for help
[libx264 @ 0x125e075a0] using SAR=1216/1215
[libx264 @ 0x125e075a0] using cpu capabilities: ARMv8 NEON
[libx264 @ 0x125e075a0] profile High, level 4.0, 4:2:0, 8-bit
[libx264 @ 0x125e075a0] 264 - core 164 r3190 7ed753b - H.264/MPEG-4 AVC codec - Copyleft 2003-2024 - http://www.videolan.org/x264.html - options: cabac=1 ref=2 deblock=1:0:0 analyse=0x3:0x113 me=hex subme=6 psy=1 psy_rd=1.00:0.00 mixed_ref=1 me_range=16 chroma_me=1 trellis=1 8x8dct=1 cqm=0 deadzone=21,11 fast_pskip=1 chroma_qp_offset=-2 threads=21 lookahead_threads=3 sliced_threads=0 nr=0 decimate=1 interlaced=0 bluray_compat=0 constrained_intra=0 bframes=3 b_pyramid=2 b_adapt=1 b_bias=0 direct=1 weightb=1 open_gop=0 weightp=1 keyint=250 keyint_min=25 scenecut=40 intra_refresh=0 rc_lookahead=30 rc=crf mbtree=1 crf=18.0 qcomp=0.60 qpmin=0 qpmax=69 qpstep=4 ip_ratio=1.40 aq=1:1.00
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0: Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
[out#0/mp4 @ 0x125e04620] video:58KiB audio:12KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 13.338576%
frame=    1 fps=0.0 q=24.0 Lsize=      79KiB time=00:00:00.03 bitrate=19369.4kbits/s speed=0.289x    
[libx264 @ 0x125e075a0] frame I:1     Avg QP:13.63  size: 58297
[libx264 @ 0x125e075a0] mb I  I16..4: 68.6% 25.1%  6.3%
[libx264 @ 0x125e075a0] 8x8 transform intra:25.1%
[libx264 @ 0x125e075a0] coded y,uvDC,uvAC intra: 28.7% 30.5% 25.8%
[libx264 @ 0x125e075a0] i16 v,h,dc,p: 97%  1%  1%  0%
[libx264 @ 0x125e075a0] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 21% 14% 14%  6%  7% 10%  7% 11%  9%
[libx264 @ 0x125e075a0] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 28% 15%  9%  6% 11% 12%  6%  9%  5%
[libx264 @ 0x125e075a0] i8c dc,h,v,p: 82%  7%  8%  3%
[libx264 @ 0x125e075a0] kb/s:13991.28
[aac @ 0x125e08890] Qavg: 65536.000
[INFO] src.freeze_effects.engine: apply_effects_to_freeze_segment: video=outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze.mp4, audio=outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav, duration=46.720, fps=30, size=1080x1920
[INFO] src.freeze_effects.engine: Effect config: white_flash=True, zoom_in=True, stinger=True
[INFO] src.freeze_effects.engine: Has audio file: True
[INFO] src.freeze_effects.engine: Video filter: [0:v]zoompan='min(1.0+0.001284246575342467*t, 1.06)':d=1401:s=1080x1920:fps=30[outv]
[INFO] src.freeze_effects.engine: Filter complex: [0:v]zoompan='min(1.0+0.001284246575342467*t, 1.06)':d=1401:s=1080x1920:fps=30[outv];[1:a]sine=f=1800:d=0.12,afade=t=out:st=0.039999999999999994:d=0.08,volume=0.5012[stinger];[0:a][stinger]amix=inputs=2:duration=first:dropout_transition=0[aout]
[INFO] src.freeze_effects.engine: Running ffmpeg with effects: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze.mp4 -i outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze_mute.wav -filter_complex [0:v]zoompan='min(1.0+0.001284246575342467*t, 1.06)':d=1401:s=1080x1920:fps=30[outv];[1:a]sine=f=1800:d=0.12,afade=t=out:st=0.039999999999999994:d=0.08,volume=0.5012[stinger];[0:a][stinger]amix=inputs=2:duration=first:dropout_transition=0[aout] -map [outv]...
[ERROR] src.freeze_effects.engine: ffmpeg failed: 13be065f0] More input link labels specified for filter 'sine' than it has inputs: 1 > 0
[AVFilterGraph @ 0x13be065f0] Error linking filters
Failed to set value '[0:v]zoompan='min(1.0+0.001284246575342467*t, 1.06)':d=1401:s=1080x1920:fps=30[outv];[1:a]sine=f=1800:d=0.12,afade=t=out:st=0.039999999999999994:d=0.08,volume=0.5012[stinger];[0:a][stinger]amix=inputs=2:duration=first:dropout_transition=0[aout]' for option 'filter_complex': Invalid argument
Error parsing global options: Invalid argument

[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -ss 248.820 -accurate_seek -i /Users/bytedance/Downloads/01.mp4 -t 6.720 -vf scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black -r 30 -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0000_post.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0000_post.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0(und): Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 aac
frame=  113 fps=0.0 q=24.0 size=    1792KiB time=00:00:03.70 bitrate=3967.7kbits/s speed=7.33x    
[out#0/mp4 @ 0x13d205110] video:3277KiB audio:106KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.255551%
frame=  202 fps=0.0 q=-1.0 Lsize=    3392KiB time=00:00:06.66 bitrate=4168.2kbits/s speed= 9.2x    
[libx264 @ 0x13d206030] frame I:2     Avg QP: 7.00  size:109132
[libx264 @ 0x13d206030] frame P:51    Avg QP: 9.88  size: 36748
[libx264 @ 0x13d206030] frame B:149   Avg QP:16.08  size:  8474
[libx264 @ 0x13d206030] consecutive B-frames:  1.5%  0.0%  1.5% 97.0%
[libx264 @ 0x13d206030] mb I  I16..4: 68.4% 24.7%  6.9%
[libx264 @ 0x13d206030] mb P  I16..4:  0.2%  2.4%  0.3%  P16..4: 12.3% 11.3%  5.9%  0.0%  0.0%    skip:67.5%
[libx264 @ 0x13d206030] mb B  I16..4:  0.4%  0.8%  0.0%  B16..8:  7.9%  3.9%  0.3%  direct: 8.4%  skip:78.3%  L0:36.6% L1:42.2% BI:21.1%
[libx264 @ 0x13d206030] 8x8 transform intra:55.2% inter:49.0%
[libx264 @ 0x13d206030] coded y,uvDC,uvAC intra: 61.8% 72.1% 64.1% inter: 10.2% 16.5% 3.0%
[libx264 @ 0x13d206030] i16 v,h,dc,p: 76%  7% 14%  4%
[libx264 @ 0x13d206030] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 24% 11% 26%  4%  7%  9%  5%  8%  7%
[libx264 @ 0x13d206030] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 25% 12% 11%  6% 11% 13%  7% 10%  6%
[libx264 @ 0x13d206030] i8c dc,h,v,p: 63% 14% 17%  7%
[libx264 @ 0x13d206030] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x13d206030] ref P L0: 59.0% 41.0%
[libx264 @ 0x13d206030] ref B L0: 83.8% 16.2%
[libx264 @ 0x13d206030] ref B L1: 97.8%  2.2%
[libx264 @ 0x13d206030] kb/s:3986.16
[aac @ 0x13d28c640] Qavg: 694.250
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i /Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0000_pre.mp4 -i /Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0000_freeze.mp4 -i /Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0000_post.mp4 -filter_complex [0:v]setpts=PTS-STARTPTS[v0];[0:a]asetpts=PTS-STARTPTS[a0];[1:v]setpts=PTS-STARTPTS[v1];[1:a]asetpts=PTS-STARTPTS[a1];[2:v]setpts=PTS-STARTPTS[v2];[2:a]asetpts=PTS-STARTPTS[a2];[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vout][aout] -map [vout] -map [aout] -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0000_segment_base.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0: Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
[out_#0:1 @ 0x10e92ba20] 100 buffers queued in out_#0:1, something may be wrong.
[out_#0:1 @ 0x10e92ba20] 1000 buffers queued in out_#0:1, something may be wrong.
frame=  136 fps=0.0 q=24.0 size=    1792KiB time=00:00:04.46 bitrate=3286.7kbits/s dup=1402 drop=0 speed=8.84x    
frame=  615 fps=609 q=24.0 size=    2304KiB time=00:00:05.07 bitrate=3717.5kbits/s dup=1402 drop=0 speed=5.03x    
frame= 1077 fps=711 q=24.0 size=    2560KiB time=00:00:05.07 bitrate=4130.5kbits/s dup=1402 drop=0 speed=3.35x    
frame= 1501 fps=744 q=24.0 size=    2816KiB time=00:00:40.55 bitrate= 568.8kbits/s dup=1402 drop=0 speed=20.1x    
frame= 1685 fps=668 q=21.0 size=    4864KiB time=00:00:56.10 bitrate= 710.3kbits/s dup=1402 drop=0 speed=22.2x    
[out#0/mp4 @ 0x11e618470] video:5748KiB audio:202KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.768752%
frame= 1757 fps=660 q=-1.0 Lsize=    5996KiB time=00:00:58.50 bitrate= 839.6kbits/s dup=1402 drop=0 speed=  22x    
[libx264 @ 0x11e624150] frame I:9     Avg QP: 5.72  size:120292
[libx264 @ 0x11e624150] frame P:445   Avg QP:10.83  size:  6691
[libx264 @ 0x11e624150] frame B:1303  Avg QP:10.32  size:  1401
[libx264 @ 0x11e624150] consecutive B-frames:  0.9%  0.6%  0.7% 97.9%
[libx264 @ 0x11e624150] mb I  I16..4: 68.5% 24.0%  7.5%
[libx264 @ 0x11e624150] mb P  I16..4:  0.1%  0.6%  0.1%  P16..4:  2.9%  2.1%  1.2%  0.0%  0.0%    skip:93.1%
[libx264 @ 0x11e624150] mb B  I16..4:  0.1%  0.2%  0.0%  B16..8:  1.5%  0.7%  0.0%  direct: 1.3%  skip:96.1%  L0:42.9% L1:41.8% BI:15.3%
[libx264 @ 0x11e624150] 8x8 transform intra:47.0% inter:55.9%
[libx264 @ 0x11e624150] coded y,uvDC,uvAC intra: 48.9% 59.0% 45.2% inter: 1.8% 3.0% 0.3%
[libx264 @ 0x11e624150] i16 v,h,dc,p: 87%  5%  6%  2%
[libx264 @ 0x11e624150] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 27% 12% 23%  4%  7%  8%  5%  8%  6%
[libx264 @ 0x11e624150] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 27% 14% 12%  5% 10% 11%  7%  8%  5%
[libx264 @ 0x11e624150] i8c dc,h,v,p: 68% 12% 15%  4%
[libx264 @ 0x11e624150] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x11e624150] ref P L0: 70.4% 29.6%
[libx264 @ 0x11e624150] ref B L0: 81.5% 18.5%
[libx264 @ 0x11e624150] ref B L1: 96.8%  3.2%
[libx264 @ 0x11e624150] kb/s:803.96
[aac @ 0x11e625460] Qavg: 52475.594
[INFO] src.render.ffmpeg_compose: Syncing narrated segment seg_0000: offset=5.060s, speech_start=0.000s, active=46.350s, seg=58.500s
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i outputs/autocut_project/compose_xhs_tmp/seg_0000_segment_base.mp4 -i outputs/autocut_project/narrations/narration_00.wav -filter_complex [0:v]setpts=PTS-STARTPTS,subtitles=/Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0000_narration.ass[vout];[0:a]asetpts=PTS-STARTPTS,volume=0.031623:enable='between(t,5.160,51.410)'[bg];[1:a]atrim=start=0.000:end=46.350,asetpts=PTS-STARTPTS,adelay=5060|5060[tts];[bg][tts]amix=inputs=2:duration=first:dropout_transition=0[aout] -map [vout] -map [aout] -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 128k -t 58.500 -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0000_segment_narrated.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x157618230] fontselect: (PingFang SC, 400, 0) -> /System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc, -1, PingFangSC-Regular
frame=  159 fps=0.0 q=24.0 size=    2048KiB time=00:00:05.23 bitrate=3205.9kbits/s speed=10.4x    
frame=  562 fps=556 q=24.0 size=    2304KiB time=00:00:18.70 bitrate=1009.3kbits/s speed=18.5x    
frame=  983 fps=649 q=24.0 size=    3072KiB time=00:00:32.70 bitrate= 769.6kbits/s speed=21.6x    
frame= 1336 fps=662 q=24.0 size=    3328KiB time=00:00:44.46 bitrate= 613.1kbits/s speed=  22x    
frame= 1628 fps=645 q=24.0 size=    4608KiB time=00:00:54.20 bitrate= 696.5kbits/s speed=21.5x    
[out#0/mp4 @ 0x15770b3c0] video:5490KiB audio:877KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 1.011135%
frame= 1755 fps=627 q=-1.0 Lsize=    6431KiB time=00:00:58.43 bitrate= 901.6kbits/s speed=20.9x    
[libx264 @ 0x157712210] frame I:9     Avg QP: 6.43  size:137311
[libx264 @ 0x157712210] frame P:450   Avg QP:10.64  size:  6297
[libx264 @ 0x157712210] frame B:1296  Avg QP:10.37  size:  1197
[libx264 @ 0x157712210] consecutive B-frames:  1.0%  1.6%  0.3% 97.1%
[libx264 @ 0x157712210] mb I  I16..4: 64.6% 24.3% 11.2%
[libx264 @ 0x157712210] mb P  I16..4:  0.1%  0.6%  0.1%  P16..4:  3.3%  2.1%  1.1%  0.0%  0.0%    skip:92.8%
[libx264 @ 0x157712210] mb B  I16..4:  0.1%  0.2%  0.0%  B16..8:  1.4%  0.6%  0.0%  direct: 1.2%  skip:96.5%  L0:41.9% L1:44.1% BI:14.0%
[libx264 @ 0x157712210] 8x8 transform intra:46.8% inter:58.1%
[libx264 @ 0x157712210] coded y,uvDC,uvAC intra: 47.8% 57.5% 41.8% inter: 1.5% 2.9% 0.2%
[libx264 @ 0x157712210] i16 v,h,dc,p: 85%  6%  7%  2%
[libx264 @ 0x157712210] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 28% 13% 24%  3%  7%  7%  5%  7%  6%
[libx264 @ 0x157712210] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 32% 18% 13%  5%  8%  8%  5%  7%  4%
[libx264 @ 0x157712210] i8c dc,h,v,p: 69% 12% 15%  4%
[libx264 @ 0x157712210] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x157712210] ref P L0: 71.3% 28.7%
[libx264 @ 0x157712210] ref B L0: 79.6% 20.4%
[libx264 @ 0x157712210] ref B L1: 96.7%  3.3%
[libx264 @ 0x157712210] kb/s:768.65
[aac @ 0x1577134e0] Qavg: 4255.287
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i outputs/autocut_project/compose_xhs_tmp/seg_0000_segment_narrated.mp4 -c copy outputs/autocut_project/compose_xhs_tmp/seg_0000_segment.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
  libswscale      8.  3.100 /  8.  3.100
  libswresample   5.  3.100 /  5.  3.100
  libpostproc    58.  3.100 / 58.  3.100
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'outputs/autocut_project/compose_xhs_tmp/seg_0000_segment_narrated.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Duration: 00:00:58.52, start: 0.045000, bitrate: 900 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], 768 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 122 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
Stream mapping:
  Stream #0:0 -> #0:0 (copy)
  Stream #0:1 -> #0:1 (copy)
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0000_segment.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 768 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 122 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
Press [q] to stop, [?] for help
[out#0/mp4 @ 0x1347111d0] video:5490KiB audio:877KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 1.010812%
frame= 1755 fps=0.0 q=-1.0 Lsize=    6431KiB time=00:00:58.45 bitrate= 901.3kbits/s speed=7.59e+03x
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -ss 256.700 -accurate_seek -i /Users/bytedance/Downloads/01.mp4 -t 18.480 -filter_complex [0:v]scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black,setpts=(PTS-STARTPTS)*(1/0.5)[vout];[0:a]asetpts=PTS-STARTPTS,atempo=0.5[aout] -map [vout] -map [aout] -t 36.960 -r 30 -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_base.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_base.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0: Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
frame=  164 fps=0.0 q=24.0 size=    1792KiB time=00:00:05.40 bitrate=2718.6kbits/s dup=114 drop=0 speed=10.7x    
frame=  376 fps=373 q=24.0 size=    4352KiB time=00:00:12.46 bitrate=2859.8kbits/s dup=220 drop=0 speed=12.4x    
frame=  590 fps=390 q=24.0 size=    7168KiB time=00:00:19.60 bitrate=2996.0kbits/s dup=327 drop=0 speed=  13x    
frame=  796 fps=395 q=24.0 size=    9728KiB time=00:00:26.46 bitrate=3011.0kbits/s dup=430 drop=0 speed=13.1x    
frame= 1002 fps=398 q=24.0 size=   12032KiB time=00:00:33.33 bitrate=2957.0kbits/s dup=533 drop=0 speed=13.2x    
[out#0/mp4 @ 0x117e04650] video:12686KiB audio:581KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.310465%
frame= 1109 fps=406 q=-1.0 Lsize=   13308KiB time=00:00:36.90 bitrate=2954.5kbits/s dup=554 drop=0 speed=13.5x    
[libx264 @ 0x117e06080] frame I:7     Avg QP: 6.35  size:119813
[libx264 @ 0x117e06080] frame P:279   Avg QP:10.13  size: 34903
[libx264 @ 0x117e06080] frame B:823   Avg QP:15.64  size:  2932
[libx264 @ 0x117e06080] consecutive B-frames:  0.9%  0.2%  0.8% 98.1%
[libx264 @ 0x117e06080] mb I  I16..4: 68.5% 24.2%  7.4%
[libx264 @ 0x117e06080] mb P  I16..4:  0.1%  0.7%  0.1%  P16..4: 11.5% 12.0%  7.2%  0.0%  0.0%    skip:68.5%
[libx264 @ 0x117e06080] mb B  I16..4:  0.1%  0.2%  0.0%  B16..8:  5.6%  1.4%  0.1%  direct: 3.7%  skip:88.9%  L0:54.0% L1:33.0% BI:13.0%
[libx264 @ 0x117e06080] 8x8 transform intra:43.9% inter:49.6%
[libx264 @ 0x117e06080] coded y,uvDC,uvAC intra: 52.9% 58.0% 55.8% inter: 7.0% 10.7% 3.3%
[libx264 @ 0x117e06080] i16 v,h,dc,p: 83%  4% 10%  2%
[libx264 @ 0x117e06080] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 25% 11% 28%  4%  6%  7%  4%  8%  7%
[libx264 @ 0x117e06080] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 26% 16%  9%  6%  9% 10%  8%  9%  6%
[libx264 @ 0x117e06080] i8c dc,h,v,p: 70% 11% 13%  5%
[libx264 @ 0x117e06080] Weighted P-Frames: Y:0.7% UV:0.4%
[libx264 @ 0x117e06080] ref P L0: 62.3% 37.7%
[libx264 @ 0x117e06080] ref B L0: 83.4% 16.6%
[libx264 @ 0x117e06080] ref B L1: 98.5%  1.5%
[libx264 @ 0x117e06080] kb/s:2811.13
[aac @ 0x117e073c0] Qavg: 702.956
[INFO] src.render.ffmpeg_compose: Syncing narrated segment seg_0001: offset=0.000s, speech_start=0.000s, active=36.960s, seg=36.960s
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_base.mp4 -i outputs/autocut_project/narrations/narration_01.wav -filter_complex [0:v]setpts=PTS-STARTPTS,subtitles=/Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0001_narration.ass[vout];[0:a]asetpts=PTS-STARTPTS,volume=0.031623:enable='between(t,0.100,36.960)'[bg];[1:a]atrim=start=0.000:end=45.550,asetpts=PTS-STARTPTS,adelay=0|0[tts];[bg][tts]amix=inputs=2:duration=first:dropout_transition=0[aout] -map [vout] -map [aout] -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 128k -t 36.960 -avoid_negative_ts make_zero outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_narrated.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] Error opening font: '/System/Library/PrivateFrameworks/FontServices.framework/Resources/Reserved/PingFangUI.ttc', 0
[Parsed_subtitles_1 @ 0x11379ef10] fontselect: (PingFang SC, 400, 0) -> /System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc, -1, PingFangSC-Regular
frame=  153 fps=0.0 q=24.0 size=    1280KiB time=00:00:05.03 bitrate=2083.3kbits/s speed=10.1x    
frame=  356 fps=355 q=24.0 size=    3840KiB time=00:00:11.80 bitrate=2665.9kbits/s speed=11.8x    
frame=  554 fps=369 q=24.0 size=    6144KiB time=00:00:18.40 bitrate=2735.4kbits/s speed=12.2x    
frame=  758 fps=378 q=24.0 size=    8704KiB time=00:00:25.20 bitrate=2829.5kbits/s speed=12.6x    
frame=  976 fps=389 q=24.0 size=   10496KiB time=00:00:32.46 bitrate=2648.4kbits/s speed=12.9x    
[out#0/mp4 @ 0x113705060] video:11737KiB audio:577KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.334370%
frame= 1109 fps=400 q=-1.0 Lsize=   12355KiB time=00:00:36.90 bitrate=2742.9kbits/s speed=13.3x    
[libx264 @ 0x11370beb0] frame I:5     Avg QP: 7.86  size:148483
[libx264 @ 0x11370beb0] frame P:388   Avg QP:10.54  size: 24789
[libx264 @ 0x11370beb0] frame B:716   Avg QP:15.59  size:  2315
[libx264 @ 0x11370beb0] consecutive B-frames:  1.1% 37.9%  1.9% 59.2%
[libx264 @ 0x11370beb0] mb I  I16..4: 60.2% 28.1% 11.7%
[libx264 @ 0x11370beb0] mb P  I16..4:  0.2%  1.1%  0.2%  P16..4: 13.5%  8.9%  6.0%  0.0%  0.0%    skip:70.2%
[libx264 @ 0x11370beb0] mb B  I16..4:  0.1%  0.1%  0.0%  B16..8:  5.3%  1.0%  0.0%  direct: 3.4%  skip:90.0%  L0:56.2% L1:34.3% BI: 9.5%
[libx264 @ 0x11370beb0] 8x8 transform intra:53.9% inter:52.9%
[libx264 @ 0x11370beb0] coded y,uvDC,uvAC intra: 59.9% 68.2% 62.7% inter: 6.9% 11.6% 2.2%
[libx264 @ 0x11370beb0] i16 v,h,dc,p: 76%  7% 13%  4%
[libx264 @ 0x11370beb0] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 26% 11% 31%  4%  5%  6%  4%  7%  6%
[libx264 @ 0x11370beb0] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 31% 19% 12%  5%  7%  8%  6%  7%  5%
[libx264 @ 0x11370beb0] i8c dc,h,v,p: 67% 13% 16%  4%
[libx264 @ 0x11370beb0] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x11370beb0] ref P L0: 79.5% 20.5%
[libx264 @ 0x11370beb0] ref B L0: 86.3% 13.7%
[libx264 @ 0x11370beb0] ref B L1: 98.4%  1.6%
[libx264 @ 0x11370beb0] kb/s:2600.90
[aac @ 0x11370d1e0] Qavg: 577.293
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_narrated.mp4 -c copy outputs/autocut_project/compose_xhs_tmp/seg_0001_segment.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
  libswscale      8.  3.100 /  8.  3.100
  libswresample   5.  3.100 /  5.  3.100
  libpostproc    58.  3.100 / 58.  3.100
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'outputs/autocut_project/compose_xhs_tmp/seg_0001_segment_narrated.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Duration: 00:00:36.99, start: 0.045000, bitrate: 2736 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], 2601 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 127 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
Stream mapping:
  Stream #0:0 -> #0:0 (copy)
  Stream #0:1 -> #0:1 (copy)
Output #0, mp4, to 'outputs/autocut_project/compose_xhs_tmp/seg_0001_segment.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2avc1mp41
    encoder         : Lavf61.7.100
  Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 2601 kb/s, 30 fps, 30 tbr, 15360 tbn (default)
      Metadata:
        handler_name    : VideoHandler
        vendor_id       : [0][0][0][0]
        encoder         : Lavc61.19.100 libx264
  Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 127 kb/s (default)
      Metadata:
        handler_name    : SoundHandler
        vendor_id       : [0][0][0][0]
Press [q] to stop, [?] for help
[out#0/mp4 @ 0x113e051e0] video:11737KiB audio:577KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.334204%
frame= 1109 fps=0.0 q=-1.0 Lsize=   12355KiB time=00:00:36.92 bitrate=2741.3kbits/s speed=5.4e+03x
[DEBUG] src.render.ffmpeg_compose: Running ffmpeg: /Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1 -y -i /Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0000_segment.mp4 -i /Users/bytedance/Downloads/autocut/outputs/autocut_project/compose_xhs_tmp/seg_0001_segment.mp4 -filter_complex [0:v]setpts=PTS-STARTPTS[v0];[0:a]asetpts=PTS-STARTPTS[a0];[1:v]setpts=PTS-STARTPTS[v1];[1:a]asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout] -map [vout] -map [aout] -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 128k -avoid_negative_ts make_zero outputs/autocut_project/compose.mp4
[DEBUG] src.render.ffmpeg_compose: ffmpeg stderr (tail):
    encoder         : Lavf61.7.100
  Stream #0:0: Video: h264 (avc1 / 0x31637661), yuv420p(tv, progressive), 1080x1920 [SAR 1216:1215 DAR 76:135], q=2-31, 30 fps, 15360 tbn
      Metadata:
        encoder         : Lavc61.19.100 libx264
      Side data:
        cpb: bitrate max/min/avg: 0/0/0 buffer size: 0 vbv_delay: N/A
  Stream #0:1: Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s
      Metadata:
        encoder         : Lavc61.19.100 aac
frame=  155 fps=0.0 q=24.0 size=    1792KiB time=00:00:05.10 bitrate=2878.5kbits/s speed=10.1x    
frame=  563 fps=560 q=24.0 size=    2304KiB time=00:00:18.70 bitrate=1009.3kbits/s speed=18.6x    
frame=  983 fps=650 q=24.0 size=    2816KiB time=00:00:32.70 bitrate= 705.5kbits/s speed=21.6x    
frame= 1395 fps=693 q=24.0 size=    3328KiB time=00:00:46.43 bitrate= 587.2kbits/s speed=23.1x    
frame= 1666 fps=661 q=24.0 size=    4864KiB time=00:00:55.46 bitrate= 718.4kbits/s speed=  22x    
frame= 1888 fps=624 q=24.0 size=    7168KiB time=00:01:02.86 bitrate= 934.1kbits/s dup=1 drop=0 speed=20.8x    
frame= 2098 fps=595 q=24.0 size=    9472KiB time=00:01:09.86 bitrate=1110.6kbits/s dup=1 drop=0 speed=19.8x    
frame= 2298 fps=570 q=24.0 size=   11776KiB time=00:01:16.53 bitrate=1260.5kbits/s dup=1 drop=0 speed=  19x    
frame= 2508 fps=553 q=24.0 size=   14080KiB time=00:01:23.53 bitrate=1380.8kbits/s dup=1 drop=0 speed=18.4x    
frame= 2722 fps=540 q=24.0 size=   16128KiB time=00:01:30.66 bitrate=1457.2kbits/s dup=1 drop=0 speed=  18x    
[out#0/mp4 @ 0x115e059d0] video:16256KiB audio:1464KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: 0.587699%
frame= 2865 fps=539 q=-1.0 Lsize=   17825KiB time=00:01:35.43 bitrate=1530.1kbits/s dup=1 drop=0 speed=17.9x    
[libx264 @ 0x115e136e0] frame I:13    Avg QP: 6.87  size:143068
[libx264 @ 0x115e136e0] frame P:938   Avg QP:11.10  size: 13149
[libx264 @ 0x115e136e0] frame B:1914  Avg QP:12.10  size:  1281
[libx264 @ 0x115e136e0] consecutive B-frames:  0.8% 29.9%  0.9% 68.3%
[libx264 @ 0x115e136e0] mb I  I16..4: 62.8% 25.5% 11.7%
[libx264 @ 0x115e136e0] mb P  I16..4:  0.1%  0.8%  0.1%  P16..4:  9.1%  4.9%  3.2%  0.0%  0.0%    skip:81.7%
[libx264 @ 0x115e136e0] mb B  I16..4:  0.1%  0.2%  0.0%  B16..8:  2.4%  0.6%  0.0%  direct: 1.7%  skip:95.1%  L0:50.5% L1:38.9% BI:10.6%
[libx264 @ 0x115e136e0] 8x8 transform intra:51.0% inter:56.5%
[libx264 @ 0x115e136e0] coded y,uvDC,uvAC intra: 52.1% 63.7% 50.5% inter: 3.4% 6.3% 0.7%
[libx264 @ 0x115e136e0] i16 v,h,dc,p: 80%  7% 10%  3%
[libx264 @ 0x115e136e0] i8 v,h,dc,ddl,ddr,vr,hd,vl,hu: 27% 13% 29%  3%  6%  7%  4%  6%  6%
[libx264 @ 0x115e136e0] i4 v,h,dc,ddl,ddr,vr,hd,vl,hu: 32% 19% 13%  5%  7%  8%  5%  7%  5%
[libx264 @ 0x115e136e0] i8c dc,h,v,p: 67% 13% 16%  4%
[libx264 @ 0x115e136e0] Weighted P-Frames: Y:0.0% UV:0.0%
[libx264 @ 0x115e136e0] ref P L0: 78.9% 21.1%
[libx264 @ 0x115e136e0] ref B L0: 84.6% 15.4%
[libx264 @ 0x115e136e0] ref B L1: 97.1%  2.9%
[libx264 @ 0x115e136e0] kb/s:1394.39
[aac @ 0x115e14dc0] Qavg: 3284.454
[INFO] src.render.ffmpeg_compose: Kept tmp dir for debugging: outputs/autocut_project/compose_xhs_tmp
[INFO] xhs_autocut: Video generated at outputs/autocut_project/compose.mp4
bytedance@CLK659JQVT autocut % 