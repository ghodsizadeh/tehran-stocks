#!/bin/sh
echo Remove the old package
pip -q  uninstall tehran-stocks-ng 

echo Clean the old compiled package
rm -fr build dist
echo Recompiling
python setup.py -q bdist_wheel

echo Reinstallation
cd dist

pip -q  install *.whl
