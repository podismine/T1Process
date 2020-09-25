import os
import subprocess
import datetime
import sys
Reference = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/templates/MNI152_T1_1mm.nii.gz'
ReferenceMask = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/templates/MNI152_T1_1mm_brain_mask.nii.gz'
Reference2mm = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/templates/MNI152_T1_2mm.nii.gz'
Reference2mmMask = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/templates/MNI152_T1_2mm_brain_mask_dil.nii.gz'
FNIRTConfig = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/config/T1_2_MNI152_2mm.cnf'
ReferenceBrain = '/home/mindsgo/yangyanwu/HCPpipelines-master/global/templates/MNI152_T1_1mm_brain.nii.gz'


def run_cmd(cmd, cmd_str='',log_path=None, verbose = 1):
    # verbose set 0 to no print
    # write log file to txt
    if log_path == None:
        log_path = './log_tmp'
    logfile = open(log_path, 'a+')
    curr_time = datetime.datetime.now()
    time_str = datetime.datetime.strftime(curr_time, '%Y-%m-%d %H:%M:%S')
    logfile.write("[" + time_str + "] "  + cmd + '\n')

    # run command
    if verbose == 1:
        if cmd_str != '':
            print("...[", cmd_str,']')
            logfile.write("[" + time_str + "] " + cmd_str + '\n')

    elif verbose == 1 or verbose == 2:
        print("[run command]: ", cmd)

    child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        outs, errs = child.communicate(timeout=60 * 60) 
    except subprocess.TimeoutExpired:
        child.kill()
        outs, errs = child.communicate()
        print('Output: ' + outs.decode('ascii'))
        print('Error: ' + errs.decode('ascii'))
        print('code: ' + str(child.returncode))

    # log error
    for line in errs.decode('ascii'):
        sys.stdout.write(line)
        logfile.write(line)
    logfile.close()

def process_pre(Image,TXwFolder):
    cmd = 'mkdir -p T1Folder/ACPCAlignment;mkdir -p T1Folder/xfms;\
        mkdir -p T1Folder/BrainExtraction_FNIRTbased;mkdir -p T1Folder/BiasFieldCorrection_T1wOnly;mkdir -p AtlasSpaceFolder/xfms'
    run_cmd(cmd, "mkdir...")
    cmd = 'fslreorient2std %s %s/%s_gdc' % (Image, TXwFolder, Image)
    run_cmd(cmd, "NOT PERFORMING GRADIENT DISTORTION CORRECTION ...")

def ACPCAlignment(Input, WD, Output,OutputMatrix):
    print('---> Start ACPC Alignment...')
    BrainSizeOpt = '-b 150'

    cmd = 'robustfov -i %s -m %s/roi2full.mat -r %s/robustroi.nii.gz %s' % (Input, WD, WD, BrainSizeOpt)
    run_cmd(cmd,'Croping the FOV...')

    cmd = 'convert_xfm -omat %s/full2roi.mat -inverse %s/roi2full.mat' % (WD, WD)
    run_cmd(cmd,'Invert the matrix (to get full FOV to ROI)...')

    cmd = 'flirt -interp spline -in %s/robustroi.nii.gz -ref %s -omat %s/roi2std.mat \
            -out %s/acpc_final.nii.gz -searchrx -30 30 -searchry -30 30 -searchrz -30 30' % (WD, Reference, WD, WD)
    run_cmd(cmd, 'Registering cropped image to MNI152 (12 DOF)...')

    cmd = 'convert_xfm -omat %s/full2std.mat -concat %s/roi2std.mat %s/full2roi.mat' % (WD, WD, WD)
    run_cmd(cmd, 'Concatenating matrices to get full FOV to MNI...')

    cmd = 'aff2rigid %s/full2std.mat %s' % (WD, OutputMatrix)
    run_cmd(cmd,'Geting a 6 DOF approximation...')

    cmd = 'applywarp --rel --interp=spline -i %s -r %s --premat=%s -o %s' % (Input, Reference, OutputMatrix, Output)
    run_cmd(cmd, 'Creating a resampled image...')
    print('---> Finished ACPC Alignment...')

def BrainExtract(Input,WD, BaseName,OutputBrainMask,OutputBrainExtractedImage):
    print('---> Start BrainExtraction FNIRT')
    cmd = 'flirt -interp spline -dof 12 -in %s -ref %s \
    -omat %s/roughlin.mat -out %s/%s_to_MNI_roughlin.nii.gz -nosearch' % (Input, Reference2mm, WD, WD, BaseName)
    run_cmd(cmd, 'linear registration to 2mm reference...')
    
    cmd = 'fnirt --in=%s --ref=%s --aff=%s/roughlin.mat \
        --refmask=%s --fout=%s/str2standard.nii.gz \
        --jout=%s/NonlinearRegJacobians.nii.gz --refout=%s/IntensityModulatedT1.nii.gz \
        --iout=%s/%s_to_MNI_nonlin.nii.gz --logout=%s/NonlinearReg.txt \
        --intout=%s/NonlinearIntensities.nii.gz --cout=%s/NonlinearReg.nii.gz \
        --config=%s' % (Input, Reference2mm, WD,Reference2mmMask, WD, WD, WD, WD, BaseName, WD, WD, WD, FNIRTConfig)
    run_cmd(cmd,'non-linear registration to 2mm reference...')

    cmd = 'applywarp --rel --interp=spline --in=%s --ref=%s \
    -w %s/str2standard.nii.gz --out=%s/%s_to_MNI_nonlin.nii.gz' % (Input, Reference, WD, WD,BaseName)
    run_cmd(cmd, 'creating spline interpolated hires version...')

    cmd = 'invwarp --ref=%s -w %s/str2standard.nii.gz -o %s/standard2str.nii.gz' % (Reference2mm,WD,WD)
    run_cmd(cmd, 'computing inverse warp...')

    cmd = 'applywarp --rel --interp=nn --in=%s --ref=%s -w \
    %s/standard2str.nii.gz -o %s' % (ReferenceMask, Input, WD, OutputBrainMask)
    run_cmd(cmd, 'applying inverse warp...')

    cmd = 'fslmaths %s -mas %s %s' % (Input, OutputBrainMask, OutputBrainExtractedImage)
    run_cmd(cmd,'creating mask...')
    print('---> Finished BrainExtraction FNIRT')

def ImgReg(T1wImage, T1wImageBrain, OutputT1wImage, OutputT1wImageBrain, OutputT1wTransform):
    cmd = 'imcp %s %s' % (T1wImage, OutputT1wImage)
    run_cmd(cmd)

    cmd = 'imcp %s %s' % (T1wImageBrain, OutputT1wImageBrain)
    run_cmd(cmd)

    cmd = 'fslmerge -t %s %s.nii.gz %s.nii.gz %s.nii.gz' % (OutputT1wTransform, T1wImage, T1wImage, T1wImage)
    run_cmd(cmd)

    cmd = 'fslmaths %s -mul 0 %s' % (OutputT1wTransform, OutputT1wTransform)
    run_cmd(cmd)

def BiasCC(T1wImage, WD, T1wBrain, oT1wImage, oT1wBrain, oBias):
    WDir = WD + '.anat'
    print('---> Start Bias Field Correction')
    cmd = 'fsl_anat -i %s -o %s --noreorient --clobber \
        --nocrop --noreg --nononlinreg --noseg --nosubcortseg  --nocleanup' %(T1wImage, WD)
    run_cmd(cmd)

    cmd = 'fslmaths %s/T1_biascorr -mas %s %s/T1_biascorr_brain' % (WDir, T1wBrain, WDir)
    run_cmd(cmd, 'masked T1_biascorr.nii.gz')

    cmd = 'imcp %s/T1_biascorr %s' % (WDir, oT1wImage)
    run_cmd(cmd, 'Copied T1_biascorr.nii.gz')

    cmd = 'imcp %s/T1_biascorr_brain %s' % (WDir, oT1wBrain)
    run_cmd(cmd, 'Copied T1_biascorr_brain.nii.gz')

    cmd = 'imcp %s/T1_fast_bias %s' % (WDir, oBias)
    run_cmd(cmd, 'Copied T1_fast_bias.nii.gz')
    print('---> Finished Bias Field Correction')

def T1Post(T1wFolder, T1wImage):
    OutputOrigT1wToT1w='OrigT1w2T1w_PreFS'
    OutputT1wImage='T1Folder/t1_acpc_dc'
    print('---> Start T1 cleaning...')
    cmd = 'convertwarp --relout --rel --ref=%s \
        --premat=%s/xfms/acpc.mat --warp1=%s/xfms/%s_dc \
        --out=%s/xfms/%s' % (Reference, T1wFolder, T1wFolder, T1wImage, T1wFolder,OutputOrigT1wToT1w)
    run_cmd(cmd)
    cmd = 'applywarp --rel --interp=spline -i %s/%s_gdc -r %s\
        -w %s/xfms/%s -o %s' % (T1wFolder, T1wImage, Reference, T1wFolder, OutputOrigT1wToT1w, OutputT1wImage)
    run_cmd(cmd)
    cmd = 'fslmaths %s -abs %s -odt float' % (OutputT1wImage, OutputT1wImage)
    run_cmd(cmd)
    cmd = 'fslmaths %s -div %s/BiasField_acpc_dc %s_restore' % (OutputT1wImage, T1wFolder, OutputT1wImage)
    run_cmd(cmd)
    cmd = 'fslmaths %s_restore -mas %s/%s_acpc_dc_brain %s_restore_brain' % (OutputT1wImage, T1wFolder, T1wImage, OutputT1wImage)
    run_cmd(cmd)
    print('---> Finished T1 cleaning...')

def FinalProcess(T1wImage, T1wRestoreBrain, WD, T1wRestoreBrainBasename,T1wRestore,\
    OutputTransform,OutputT1wImage,OutputT1wImageRestore,OutputT1wImageRestoreBrain):
    print('---> Start T1 To MNI normalizing...')

    cmd = 'flirt -interp spline -dof 12 -in %s -ref %s \
        -omat %s/xfms/acpc2MNILinear.mat -out %s/xfms/%s_to_MNILinear' % (T1wRestoreBrain, ReferenceBrain, WD, WD, T1wRestoreBrainBasename)
    run_cmd(cmd,'Linear then non-linear registration to MNI')

    cmd = 'fnirt --in=%s --ref=%s --aff=%s/xfms/acpc2MNILinear.mat \
            --refmask=%s --fout=%s --jout=%s/xfms/NonlinearRegJacobians.nii.gz\
            --refout=%s/xfms/IntensityModulatedT1.nii.gz --iout=%s/xfms/2mmReg.nii.gz --logout=%s/xfms/NonlinearReg.txt \
            --intout=%s/xfms/NonlinearIntensities.nii.gz --cout=%s/xfms/NonlinearReg.nii.gz --config=%s'\
      % (T1wRestore, Reference2mm, WD,Reference2mmMask,OutputTransform, WD, WD, WD, WD, WD, WD, FNIRTConfig)
    run_cmd(cmd)

    #cmd = 'invwarp -w ${} -o ${} -r ${}' % (OutputTransform, OutputInvTransform, Reference2mm)
    #run_cmd(cmd, 'Computing 2mm warp')

    cmd = 'applywarp --rel --interp=spline -i %s -r %s -w %s -o %s' % (T1wImage, Reference, OutputTransform, OutputT1wImage)
    run_cmd(cmd, 'Generarting T1w set of warped outputs')

    cmd = 'applywarp --rel --interp=spline -i %s -r %s -w %s -o %s' % (T1wRestore, Reference, OutputTransform, OutputT1wImageRestore)
    run_cmd(cmd)

    cmd = 'applywarp --rel --interp=nn -i %s -r %s -w %s -o %s' % (T1wRestoreBrain, Reference, OutputTransform, OutputT1wImageRestoreBrain)
    run_cmd(cmd)

    cmd = 'fslmaths %s -mas %s %s' % (OutputT1wImageRestore, OutputT1wImageRestoreBrain, OutputT1wImageRestoreBrain)
    run_cmd(cmd)
    print('---> Finished T1 To MNI normalizing...')
 
def T1Process():
    process_pre('t1','T1Folder')
    ACPCAlignment('T1Folder/t1_gdc.nii.gz', 'T1Folder/ACPCAlignment', 'T1Folder/t1_acpc', 'T1Folder/xfms/acpc.mat')
    BrainExtract('T1Folder/t1_acpc', 'T1Folder/BrainExtraction_FNIRTbased', 't1_acpc', 'T1Folder/t1_acpc_brain_mask','T1Folder/t1_acpc_brain')
    ImgReg('T1Folder/t1_acpc','T1Folder/t1_acpc_brain',  'T1Folder/t1_acpc_dc', 'T1Folder/t1_acpc_dc_brain','T1Folder/xfms/t1_dc')
    BiasCC('T1Folder/t1_acpc_dc', 'T1Folder/BiasFieldCorrection_T1wOnly', \
            'T1Folder/t1_acpc_dc_brain', 'T1Folder/t1_acpc_dc_restore', 'T1Folder/t1_acpc_dc_restore_brain', 'T1Folder/BiasField_acpc_dc')
    T1Post('T1Folder', 't1')

    FinalProcess('T1Folder/t1_acpc_dc','T1Folder/t1_acpc_dc_restore_brain', 'AtlasSpaceFolder','t1','T1Folder/t1_acpc_dc_restore', \
        'AtlasSpaceFolder/xfms/acpc_dc2standard.nii.gz', 'AtlasSpaceFolder/t1','AtlasSpaceFolder/t1_restore','AtlasSpaceFolder/t1_restore_brain')


# Usage
# Like this
df = pd.read_csv("../IXI_data_index.csv")
ages = list(df['AGE'])
pths = list(df['pth'])

assert len(ages) == len(pths)

start_num = 0
for age, pth in zip(ages, pths):
    print("conducting... No." + str(start_num))
    name = pth.split('/')[-1].split('-')[0] + '_' + str(age)
    run_cmd("mkdir -p " + name)
    run_cmd("cp " + pth + " ./" + name + '/')
    run_cmd("cp " + pth + " ./" + name + '/t1.nii.gz')
    os.chdir("/data1/yangyanwu_workplace/brain_age/preprocess/" + name)
    run_cmd("cd /data1/yangyanwu_workplace/brain_age/preprocess/" + name)
    T1Process()
    os.chdir("/data1/yangyanwu_workplace/brain_age/preprocess")
    run_cmd("cd /data1/yangyanwu_workplace/brain_age/preprocess")
    start_num += 1