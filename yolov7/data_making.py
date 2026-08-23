import cv2
import os

# ================= 配置区域 =================
# 1. 存放所有视频的文件夹路径 (注意最后不要加视频文件名，只写到文件夹即可)
input_video_dir = "D:/pycharm_projects/yolov7-main/yolov7-main/mydata/video3"

# 2. 存放提取出图片的文件夹路径
output_image_dir = "D:/pycharm_projects/yolov7-main/yolov7-main/mydata/images"

# 3. 抽帧间隔 (30代表每30帧抽1张，约等于1秒1张)
save_step = 25
# ============================================

# 自动创建保存图片的文件夹
if not os.path.exists(output_image_dir):
    os.makedirs(output_image_dir)

# 获取输入文件夹下所有的 .mp4 文件列表
video_files = [f for f in os.listdir(input_video_dir) if f.endswith('.mp4')]

if len(video_files) == 0:
    print(f"在 {input_video_dir} 目录下没有找到 .mp4 视频文件，请检查路径！")
else:
    print(f"共找到 {len(video_files)} 个视频文件，准备开始处理...\n")

    global_saved_count = 1200  # 全局图片计数器，保证所有视频生成的图片名字不重复

    # 循环遍历每一个视频文件
    for idx, video_name in enumerate(video_files):
        # 拼接当前视频的完整路径
        video_path = os.path.join(input_video_dir, video_name)

        print(f"正在处理第 {idx + 1}/{len(video_files)} 个视频: {video_name} ...")

        # 打开当前视频
        video = cv2.VideoCapture(video_path)

        if not video.isOpened():
            print(f"  --> 警告：视频 {video_name} 无法打开，已跳过。")
            continue

        frame_num = 0  # 当前视频的帧数计数器

        while True:
            ret, frame = video.read()
            if not ret:
                break  # 当前视频读完了，跳出内层循环

            frame_num += 1

            # 满足间隔条件，保存图片
            if frame_num % save_step == 0:
                global_saved_count += 1

                # 生成带前导零的图片名字，例如 frame_00001.jpg, frame_00002.jpg
                # 这样在文件夹里查看时排序会非常整齐，方便打标签
                save_name = f"img_{global_saved_count:05d}.jpg"
                save_path = os.path.join(output_image_dir, save_name)

                cv2.imwrite(save_path, frame)

        # 释放当前视频资源
        video.release()

    print(f"\n全部处理完成！所有视频共计提取了 {global_saved_count} 张图片。")
    print(f"图片已保存在: {output_image_dir}")