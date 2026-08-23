@echo off
REM ============================================================
REM Resume clean-data YOLOv7 ablation experiments on Windows.
REM First resumes ablation_clean_baseline_full, then trains the
REM remaining clean-data ablation variants.
REM Usage: resume_ablation_clean.bat [epochs] [batch_size] [device]
REM Example: resume_ablation_clean.bat 100 6 0
REM ============================================================

SET EPOCHS=%1
IF "%EPOCHS%"=="" SET EPOCHS=100

SET BATCH=%2
IF "%BATCH%"=="" SET BATCH=6

SET DEVICE=%3
IF "%DEVICE%"=="" SET DEVICE=0

SET CFG=D:/pycharm_projects/yolov7-main/yolov7-main/cfg/training/yolov7.yaml
SET DATA=D:/pycharm_projects/yolov7-main/yolov7-main/mydata_YOLO_clean/data.yaml
SET HYP=data/hyp.scratch.p5.yaml
SET WEIGHTS=yolov7.pt
SET BASELINE_LAST=D:/pycharm_projects/yolov7-main/yolov7-main/runs/train/ablation_clean_se_full/weights/last.pt

ECHO ============================================================
ECHO Resuming clean-data ablation experiments
ECHO Epochs=%EPOCHS%  Batch=%BATCH%  Device=%DEVICE%
ECHO Data=%DATA%
ECHO ============================================================

REM ------ Experiment 1: resume Baseline ----------------------
IF EXIST "%BASELINE_LAST%" (
    ECHO.
    ECHO [2/4] Baseline: resume ablation_clean_se_full
    python train.py --resume "%BASELINE_LAST%"
    IF ERRORLEVEL 1 GOTO :error
) ELSE (
    ECHO.
    ECHO [2/4] SE: attention=se, loss=bce
    python train.py ^
    --weights %WEIGHTS% ^
    --cfg %CFG% ^
    --data %DATA% ^
    --hyp %HYP% ^
    --epochs %EPOCHS% ^
    --batch-size %BATCH% ^
    --device %DEVICE% ^
    --name ablation_clean_se_full ^
    --attention se ^
    --loss bce
IF ERRORLEVEL 1 GOTO :error
)


REM ------ Experiment 3: Focal Loss, no attention -------------
ECHO.
ECHO [3/4] Focal: attention=none, loss=focal
python train.py ^
    --weights %WEIGHTS% ^
    --cfg %CFG% ^
    --data %DATA% ^
    --hyp %HYP% ^
    --epochs %EPOCHS% ^
    --batch-size %BATCH% ^
    --device %DEVICE% ^
    --name ablation_clean_focal_full ^
    --attention none ^
    --loss focal ^
    --fl-gamma 1.5 ^
    --fl-alpha 0.25
IF ERRORLEVEL 1 GOTO :error

REM ------ Experiment 4: SE + Focal Loss ----------------------
ECHO.
ECHO [4/4] SE+Focal: attention=se, loss=focal
python train.py ^
    --weights %WEIGHTS% ^
    --cfg %CFG% ^
    --data %DATA% ^
    --hyp %HYP% ^
    --epochs %EPOCHS% ^
    --batch-size %BATCH% ^
    --device %DEVICE% ^
    --name ablation_clean_se_focal_full ^
    --attention se ^
    --loss focal ^
    --fl-gamma 1.5 ^
    --fl-alpha 0.25
IF ERRORLEVEL 1 GOTO :error

ECHO.
ECHO ============================================================
ECHO All experiments finished. Collecting plots...
ECHO ============================================================
python eval_ablation.py --preset clean --output ablation_results_clean.csv
python plot_ablation.py --csv ablation_results_clean.csv --out_dir figures_clean
GOTO :end

:error
ECHO.
ECHO [ERROR] Experiment failed. Check the output above.
EXIT /B 1

:end
ECHO Done.
