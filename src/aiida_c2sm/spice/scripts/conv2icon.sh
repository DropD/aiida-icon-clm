#!/usr/local/bin/bash
export PMI_NO_FORK=1
export PMI_NO_PREINITIALIZE=1
export PMI_MMAP_SYNC_WAIT_TIME=300

set -e

source ./inputs.sh  # get variables

WORKDIR=$PWD

mkdir $WORKDIR/outfiles

DATAFILELIST=$(find $WORKDIR/gcm_prepared/${GCM_PREFIX}??????????.nc)

if [ ${CURRENT_DATE} -eq ${YDATE_START}  ]
then

  cdo -s selname,LSM $WORKDIR/gcm_prepared/${GCM_PREFIX}${YDATE_START}.nc $WORKDIR/boundary_data/input_FR_LAND.nc
  ncrename -h -v LSM,FR_LAND $WORKDIR/boundary_data/input_FR_LAND.nc
  cdo -s selname,FR_LAND ${EXTPAR} $WORKDIR/boundary_data/output_FR_LAND.nc
  ncecat -O -u time $WORKDIR/boundary_data/output_FR_LAND.nc $WORKDIR/boundary_data/output_FR_LAND.nc # add time dimension otherwise ICON stops
  ncks -h -A -v time $WORKDIR/boundary_data/input_FR_LAND.nc $WORKDIR/boundary_data/output_FR_LAND.nc # give time a value to avoid CDO warnings
  cdo -L -s setctomiss,0. -ltc,0.5  $WORKDIR/boundary_data/input_FR_LAND.nc $WORKDIR/boundary_data/input_ocean_area.nc
  cdo -L -s  setctomiss,0. -gec,0.5 $WORKDIR/boundary_data/input_FR_LAND.nc $WORKDIR/boundary_data/input_land_area.nc
  cdo -L -s setctomiss,0. -ltc,1. $WORKDIR/boundary_data/output_FR_LAND.nc $WORKDIR/boundary_data/output_ocean_area.nc
  cdo -L -s  setctomiss,0. -gtc,0. $WORKDIR/boundary_data/output_FR_LAND.nc $WORKDIR/boundary_data/output_land_area.nc
  cdo -s setrtoc2,0.5,1.0,1,0 $WORKDIR/boundary_data/output_FR_LAND.nc $WORKDIR/outfiles/output_lsm.nc
  rm $WORKDIR/boundary_data/input_FR_LAND.nc $WORKDIR/boundary_data/output_FR_LAND.nc


  # create file with ICON grid information for CDO
  cdo -s selgrid,2 ${LAM_GRID} $WORKDIR/boundary_data/triangular-grid.nc

  # remap land area only variables (ocean points are assumed to be undefined in the input data)
  cdo -s setmisstodis -selname,SMIL1,SMIL2,SMIL3,SMIL4,STL1,STL2,STL3,STL4,W_SNOW,T_SNOW $WORKDIR/gcm_prepared/${GCM_PREFIX}${YDATE_START}.nc  \
                                       $WORKDIR/outfiles/tmpl1.nc
  cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc $WORKDIR/outfiles/tmpl1.nc $WORKDIR/outfiles/tmpl2.nc
  cdo -s div $WORKDIR/outfiles/tmpl2.nc $WORKDIR/boundary_data/output_land_area.nc $WORKDIR/outfiles/tmp_output_l.nc
  rm $WORKDIR/outfiles/tmpl?.nc

  # remap land and ocean area differently for variables
  # ocean part
  cdo -s selname,SKT $WORKDIR/gcm_prepared/${GCM_PREFIX}${YDATE_START}.nc $WORKDIR/outfiles/tmp_input_ls.nc
  cdo -s div $WORKDIR/outfiles/tmp_input_ls.nc $WORKDIR/boundary_data/input_ocean_area.nc  $WORKDIR/outfiles/tmpls1.nc
  cdo -s setmisstodis $WORKDIR/outfiles/tmpls1.nc $WORKDIR/outfiles/tmpls2.nc
  cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc $WORKDIR/outfiles/tmpls2.nc $WORKDIR/outfiles/tmpls3.nc
  cdo -s div $WORKDIR/outfiles/tmpls3.nc $WORKDIR/boundary_data/output_ocean_area.nc $WORKDIR/outfiles/tmp_ocean_part.nc
  rm $WORKDIR/outfiles/tmpls?.nc
  # land part
  cdo -s div $WORKDIR/outfiles/tmp_input_ls.nc $WORKDIR/boundary_data/input_land_area.nc  $WORKDIR/outfiles/tmpls1.nc
  cdo -s setmisstodis $WORKDIR/outfiles/tmpls1.nc $WORKDIR/outfiles/tmpls2.nc
  cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc $WORKDIR/outfiles/tmpls2.nc $WORKDIR/outfiles/tmpls3.nc
  cdo -s div $WORKDIR/outfiles/tmpls3.nc $WORKDIR/boundary_data/output_land_area.nc $WORKDIR/outfiles/tmp_land_part.nc
  rm $WORKDIR/outfiles/tmpls?.nc
  # merge remapped land and ocean part
  cdo -s ifthenelse $WORKDIR/outfiles/output_lsm.nc $WORKDIR/outfiles/tmp_land_part.nc  $WORKDIR/outfiles/tmp_ocean_part.nc $WORKDIR/outfiles/tmp_output_ls.nc
  rm $WORKDIR/outfiles/tmp_land_part.nc $WORKDIR/outfiles/tmp_ocean_part.nc

  # remap the rest
  ncks -h -O -x -v W_SNOW,T_SNOW,STL1,STL2,STL3,STL4,SMIL1,SMIL2,SMIL3,SMIL4,SKT,LSM $WORKDIR/gcm_prepared/${GCM_PREFIX}${YDATE_START}.nc $WORKDIR/outfiles/tmp_input_rest.nc
  cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc $WORKDIR/outfiles/tmp_input_rest.nc $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc

   # merge remapped files plus land sea mask from EXTPAR
  ncks -h -A $WORKDIR/outfiles/tmp_output_l.nc $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncks -h -A $WORKDIR/outfiles/tmp_output_ls.nc $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncks -h -A $WORKDIR/outfiles/output_lsm.nc  $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  rm -f $WORKDIR/outfiles/tmp_output_l.nc $WORKDIR/outfiles/tmp_output_ls.nc $WORKDIR/outfiles/tmp_input_ls.nc $WORKDIR/outfiles/tmp_input_rest.nc

  # attribute modifications
  ncatted -h -a coordinates,FR_LAND,o,c,"clon clat" $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc

  # renamings
  ncrename -h -v FR_LAND,LSM $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncrename -h -v SIC,CI $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncrename -h -d level,lev $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncrename -h -d cell,ncells $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc
  ncrename -h -d nv,vertices $WORKDIR/boundary_data/${GCM_PREFIX}${YDATE_START}_ini.nc

  #   The vertical coordinate coefficients has not been transfered by CDO. They have to be added here again.
  pushd $WORKDIR/boundary_data
  ncks -h -O -C -v ak,bk $WORKDIR/gcm_prepared/${GCM_PREFIX}${YYYY}${MM}0100.nc hyai_hybi.nc
  ncatted -h -a ,global,d,,  hyai_hybi.nc
  ncrename -d level1,nhyi hyai_hybi.nc
  ncrename -v ak,hyai hyai_hybi.nc
  ncrename -v bk,hybi hyai_hybi.nc

  ncks -h -A $WORKDIR/boundary_data/hyai_hybi.nc ${GCM_PREFIX}${YDATE_START}_ini.nc

fi # end remapping initial data

# ----------------------------------------------------------------------------
# PART II: Extract lower boundary data
# ----------------------------------------------------------------------------
rm -f $WORKDIR/outfiles/${GCM_PREFIX}${YYYY}${MM}_tmp.nc

ncrcat -h -v SIC,SST $WORKDIR/gcm_prepared/${GCM_PREFIX}??????????.nc  \
                 $WORKDIR/outfiles/${GCM_PREFIX}${YYYY}${MM}_tmp.nc

cdo -s setmisstodis -selname,SIC $WORKDIR/outfiles/${GCM_PREFIX}${YYYY}${MM}_tmp.nc \
                                $WORKDIR/outfiles/SIC_${YYYY}${MM}_tmp.nc

cdo -s setmisstodis -selname,SST $WORKDIR/outfiles/${GCM_PREFIX}${YYYY}${MM}_tmp.nc  \
                                 $WORKDIR/outfiles/SST_${YYYY}${MM}_tmp.nc

cdo -s merge $WORKDIR/outfiles/SST_${YYYY}${MM}_tmp.nc  \
             $WORKDIR/outfiles/SIC_${YYYY}${MM}_tmp.nc  \
             $WORKDIR/outfiles/SST-SIC_${YYYY}${MM}_tmp.nc

cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc \
               $WORKDIR/outfiles/SST-SIC_${YYYY}${MM}_tmp.nc  \
               $WORKDIR/outfiles/SST-SIC_${YYYY}${MM}_${GCM_REMAP}_tmp.nc

cdo -s div $WORKDIR/outfiles/SST-SIC_${YYYY}${MM}_${GCM_REMAP}_tmp.nc $WORKDIR/boundary_data/output_ocean_area.nc \
           $WORKDIR/outfiles/LOWBC_${YYYY}_${MM}.nc

#Clean up
rm -f $WORKDIR/outfiles/*_tmp.*

#-----------------------------------------------------------------------------
# PART III: Extract lateral boundary data
#-----------------------------------------------------------------------------
echo ----- start CONV2ICON for LATBC

#   The vertical coordinate coefficients has not been transfered by iconremap due to an error in the cdilib.
#   They have to be added here again.
pushd $WORKDIR/outfiles

COUNTPP=0
for FILE in ${DATAFILELIST}
do
(
  FILEOUT=$(basename ${FILE} .nc)
  cdo -s -P ${OMP_THREADS_CONV2ICON} ${GCM_REMAP},$WORKDIR/boundary_data/triangular-grid.nc -selname,T,U,V,W,LNPS,GEOP_ML,QV,QC,QI${ICON_INPUT_OPTIONAL} ${FILE} $WORKDIR/outfiles/${FILEOUT}_lbc.nc
  ncks -h -A $WORKDIR/boundary_data/hyai_hybi.nc $WORKDIR/outfiles/${FILEOUT}_lbc.nc
   ncrename -d level,lev $WORKDIR/outfiles/${FILEOUT}_lbc.nc
   ncrename -d cell,ncells $WORKDIR/outfiles/${FILEOUT}_lbc.nc
   ncrename -d nv,vertices $WORKDIR/outfiles/${FILEOUT}_lbc.nc
)&
    (( COUNTPP=COUNTPP+1 ))
    if [ ${COUNTPP} -ge ${MAX_PP} ]
    then
      COUNTPP=0
      wait
    fi
done
wait

if [ ${CURRENT_DATE} -eq ${YDATE_START}  ]
then
   cp $WORKDIR/outfiles/${GCM_PREFIX}${YDATE_START}_lbc.nc $WORKDIR/boundary_data
fi

#-----------------------------------------------------------------------------
# clean-up
#-----------------------------------------------------------------------------

if [ ${CLEANUP_PREVIOUS} -eq 1 ]
then
  rm -r $WORKDIR/gcm_prepared
fi
