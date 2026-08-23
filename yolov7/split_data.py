import os
import random
import shutil

# ==================== 配置区域 ====================
# 1. 你当前所有图片和标签所在的文件夹路径 (写绝对路径最安全)
src_images_dir = r"D:\pycharm_projects\yolov7-main\yolov7-main\mydata\images"
src_labels_dir = r"D:\pycharm_projects\yolov7-main\yolov7-main\mydata\labels"

# 2. 划分后，新数据集存放的【总目标文件夹】
# 脚本会自动在这里面创建 images/train, labels/train 等子文件夹
target_base_dir = r"D:\pycharm_projects\yolov7-main\yolov7-main\mydata_YOLO_new"

# 3. 训练集所占的比例 (通常 0.8 或 0.9，剩下的自动给验证集 valid)
train_ratio = 0.8


# ==================================================

def create_dirs(base_path):
    """自动创建 YOLO 标准的文件夹结构"""
    dirs_to_make = [
        os.path.join(base_path, 'images', 'train'),
        os.path.join(base_path, 'images', 'val'),
        os.path.join(base_path, 'labels', 'train'),
        os.path.join(base_path, 'labels', 'val')
    ]
    for d in dirs_to_make:
        os.makedirs(d, exist_ok=True)
    return dirs_to_make


def split_dataset():
    print("开始检查文件...")
    # 获取所有的图片文件 (支持 jpg, png 等常见格式)
    valid_extensions = ['.jpg', '.jpeg', '.png']
    image_files = [f for f in os.listdir(src_images_dir) if os.path.splitext(f)[1].lower() in valid_extensions]

    # 过滤掉没有对应 txt 标签的图片 (防止漏打标签的废图混进去报错)
    valid_pairs = []
    for img_name in image_files:
        base_name = os.path.splitext(img_name)[0]
        txt_name = base_name + '.txt'

        if os.path.exists(os.path.join(src_labels_dir, txt_name)):
            valid_pairs.append((img_name, txt_name))

    total_files = len(valid_pairs)
    if total_files == 0:
        print("❌ 没有找到成对的图片和标签，请检查你的路径对不对！")
        return

    print(f"共找到 {total_files} 对有效的图片和标签，开始打乱划分...")

    # 随机打乱数据，保证训练集和验证集的多样性
    random.shuffle(valid_pairs)

    # 计算划分的索引点
    train_size = int(total_files * train_ratio)

    train_files = valid_pairs[:train_size]
    val_files = valid_pairs[train_size:]

    # 创建目标文件夹
    create_dirs(target_base_dir)

    print(f"-> 准备将 {len(train_files)} 张分配给 训练集 (train)")
    print(f"-> 准备将 {len(val_files)} 张分配给 验证集 (val)")

    # 开始复制文件
    for i, (img, txt) in enumerate(train_files):
        shutil.copy(os.path.join(src_images_dir, img), os.path.join(target_base_dir, 'images', 'train', img))
        shutil.copy(os.path.join(src_labels_dir, txt), os.path.join(target_base_dir, 'labels', 'train', txt))

    for i, (img, txt) in enumerate(val_files):
        shutil.copy(os.path.join(src_images_dir, img), os.path.join(target_base_dir, 'images', 'val', img))
        shutil.copy(os.path.join(src_labels_dir, txt), os.path.join(target_base_dir, 'labels', 'val', txt))

    print(f"🎉 划分完成！请去 {target_base_dir} 目录下查看你的 YOLO 数据集！")


if __name__ == '__main__':
    split_dataset()