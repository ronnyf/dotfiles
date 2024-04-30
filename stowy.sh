#!/usr/bin/env sh

target_file_name="target.stowy"
current=`pwd`

for entry in "${current}"/*; do
	target_path="${entry}/${target_file_name}"
	if [ -e "${target_path}" ]; then
		package=`basename ${entry}`
		echo "stowy package ${package} >>> begin"

		target=$(<$target_path)
		if [ ! -d "${target}" ]; then
			eval "mkdir -p ${target}"
		fi

		stow_target="${target}"
		cmd="stow -t "${target}" -v ${package} --dotfiles --ignore=^target\.stowy$ --ignore=\.DS_Store"
		#echo "cmd: ${cmd}"
		eval "${cmd}"
		#result=${!cmd}

		echo "stowy package ${package} <<< done" 
	fi
done

