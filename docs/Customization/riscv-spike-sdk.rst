sycuricon( 一 ): riscv-spike-sdk
========================================

谨以这个系列文章，献给我们的 syscuricon 小队。
emmm~，phantom yyds！！！！ 

简介
~~~~~~~~~~~~~~~~~~~~~~~~~~~~`

starship 是 sycuricon 提供的 RISCV 处理器自动化仿真、验证、综合平台，基于该平台已经实现了十余个工程项目，并发布多篇论文。

starship 提供了平台的硬件实现，而 riscv-spike-sdk 为 starship 提供了配套的工具链和软件，两者相辅相成，确保平台的各个 flow 可以正确运行。

目录结构如下：

.. code:: text

    .
    ├── build           # 存放编译结果
    ├── conf            # 存放配置文件
    ├── LICENSE         # 证书
    ├── Makefile        
    ├── quickstart.sh   # 快速执行脚本，你可以用一步到位编译仿真
    ├── README.md                
    ├── repo
    │   ├── buildroot           # busy boy，initramfs
    │   ├── linux               # linux kernel
    │   ├── openocd             # 片外调试器
    │   ├── opensbi             # bootloader + sbi
    │   ├── riscv-gnu-toolchain # riscv 工具链，如 gcc、gdb 等
    │   ├── riscv-isa-sim       # riscv 仿真模拟器
    │   └── riscv-pk            # bootloader + sbi
    ├── rootfs                  # buidlroot 编译和存放编译结果的目录
    └── toolchain       # 工具链，编译生成的工具链会被存在这里

想要快速了解本工程的朋友可以阅读 riscv-spike-sdk 的 README，然后一键运行 quickstart.sh。这个脚本会下载所有必须的子模块，然后编译必须的工具链、模拟器、软件镜像，然后在模拟器上启动一个 linux kernel。

系统启动
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

考虑到部分使用者还只是和我一样的大学生，对于计算机系统了解有限，因此在这里通过讲解 starship 系统启动的过程，来介绍 riscv-spike-sdk 各个组件的功能。

starship 的 SoC 有四个启动相关的存储部件：
- 启动阶段 0 的 zero stage bootloader 存放在硬件模块 boot rom 上，起始地址是 0x10000
- 启动阶段 1 的 first stage bootloader 存放在硬件模块 mask rom 上，起始地址是 0x20000
- 系统镜像存储在 spi 总线连接的外部 SD 卡分区内
- 片外 ddr 实现的内存，起始地址是 0x80000000

1. 当 starship 上电启动的时候，处理器内部的 PC 寄存器会被初始化为 0x10000，处理器开始执行 0x10000 内部的程序。这部分程序做一些简单的寄存器初始化，然后跳转到 0x20000，执行 maskrom 上的启动代码。
2. maskrom 的启动代码是一个 SD 卡读驱动程序，这个程序会用 MMIO 的方式访问 SPI 总线，将 SD 卡内的镜像读出，然后写到 ddr 上，这个过程非常费时。待读取完毕后，处理器跳转到 0x80000000 开始执行系统镜像。
3. 系统镜像由 bootloader、linux kernel、initramfs 三部分组成。在构造系统镜像的时候，initramfs 会被作为 linux kernel 的数据部分，一起编译得到 kernel 镜像；之后 kernel 镜像会被作为 bootloader 的数据部分，一起编译为 bootloader。所以 SD 卡内部存储的 bootloader 其实是 bootloader 的代码段、数据段，外加上 kernel 和 initramfs 二进制数据的 payload 段。
4. 当系统镜像被 maskrom 加载到 memor 之后，bootloader 的代码段就位于 0x80000000 地址开始，0x80000000 地址的第一条指令就是 bootloader 的第一条指令，于是处理器开始执行 bootloader 进行物理模式的初始化，包括设置 M 态寄存器，设置地址范围保护，初始化各个外部寄存器，初始化 sbi 调用。然后 bootloader 将 payload 段的 kernel 镜像加载到内存中合适的位置，然后跳到 kernel 的起始地址开始执行。
5. kernel 镜像也由 kernel 的代码段、数据段和 payload 的 initramfs 组成的。处理器执行 kernel 完成 S 态的寄存器初始化、页表设置、进程设置、网络设置、文件系统设置等等，然后将 initramfs 载入到合适的内存地址，然后进入用户态，开始执行 initramfs 中的初始化程序。
6. 初始化完毕后，处理器执行 shell 程序，为操作系统和文件系统起一个简单的 shell，方便用户进行交互。

此外：
- bootloader 可以选择使用 opensbi 或者 riscv-pk
- kernel 就是 linux kernel
- 在 bootloader 和 kernel 之间可以额外加入一个 uboot
- 除了 initramfs 可以额外挂载 debain、ubuntu 等文件系统，这需要在 SD 中创建额外的分区，修改系统配置。

riscv-gnu-toolchain
~~~~~~~~~~~~~~~~~~~~~~~

riscv-gnu-toolchain 是 GNU 提供的 RISCV 指令级的工具链，包括 riscv 的汇编器 as、编译器 gcc、反汇编器 objdump、调试器 gdb、链接器 ld 等。因为我们需要在 x86、arm 等处理器上编译得到 riscv 指令集的系统镜像，所以我们需要构造 RISCV 指令集的交叉编译器。

riscv-gnu-toolchain 可以编译提供了两套工具链：
- riscv-unknown-linux-gnu：该工具链可以编译 linux 操作系统的程序，提供 glibc 作为运行时库，可以编译 linux 内核并且可以调用 linux 提供的 api。我们后续编译 linux 等主要是用这个工具链。
- riscv-unknown-elf：该工具链可以编译代码得到简单的 elf 程序，往往被用于编译相对简单的嵌入式 C 程序，使用的 C 运行库是 newlib，因此也不能调用 linux 的 api 和 glibc 的库函数。这个工具链一般被用于生成各类测试程序，这些程序可以把简短运行库打包作为整体，不依赖动态运行库运行，并且 elf 生成的程序相较于 linux 生成的程序更加的简短，适合模拟器、嵌入式等外部执行环境。

编译 riscv-unknown-linux-gnu-toolchain
--------------------------------------

在编译之前首先同步需要的子模块。首先同步 riscv-gnu-toolchain 模块，因为riscv-unknown-linux-gnu-toolchain 作为编译 linux 和调用 linux api 的工具链需要知道 linux 的头文件信息，所以需要额外同步 linux 模块。

之后同步 riscv-gnu-toolchain 的子模块。不是所有子模块都需要同步的，同步编译工具链必要模块即可。

.. code:: sh

        git submodule update --init repo/riscv-gnu-toolchian
        git submodule update --init repo/linux
        cd repo/riscv-gnu-toolchain
        git submodule update --init binutils
        git submodule update --init gcc
        git submodule update --init glibc
        git submodule update --init newlibc
        git submodule update --init gdb



之后设置一些编译参数：
- RISCV 变量是 RISCV 工具链的地址目录，这里默认是 toolchain 目录。当需要使用 RISCV 工具的时候会从这个目录开始寻找，当需要安装 RISCV 工具链的时候则会安装到这个地址。
- ISA 变量是编译使用的指令集扩展，这里默认的是`rv64imafdc_zifencei_zicsr`。rv64 表示是 64 位的 RISCV 指令级，imafdc 分别是整数、乘除法、原子、单精度浮点、双精度浮点、压缩指令集扩展，zifencei 是屏障指令集扩展，zicsr 是特权指令集扩展。这个参数被用于编译器的生成和后续编译器的调用。该参数需要和软件执行的处理器和模拟器的 arch 相统一。
- ABI 是应用二进制接口，也就是读函数传参寄存器的定义，lp64 指整数和指针用 64 位整数寄存器传参，d 指浮点用双精度浮点寄存器传参。这个参数被用于编译器的生成和后续编译器的调用。该参数需要确保所有的软件相统一。

.. code-block:: Makefile

    RISCV ?= $(CURDIR)/toolchain
    PATH := $(RISCV)/bin:$(PATH)
    ISA ?= rv64imafdc_zifencei_zicsr
    ABI ?= lp64d

编译相关的 target 如下。可以看到，首先将 linux 中的头文件安装到 build/toolchain 当中，然后配置 toolchain 编译的编译目录、安装目录、isa 和 abi 参数，之后编译 toolchain 即可。

.. code-block:: Makefile

        wrkdir := $(CURDIR)/build
        toolchain_srcdir := $(srcdir)/riscv-gnu-toolchain
        toolchain_wrkdir := $(wrkdir)/riscv-gnu-toolchain
        toolchain_dest := $(CURDIR)/toolchain
        target_linux  := riscv64-unknown-linux-gnu

        $(toolchain_dest)/bin/$(target_linux)-gcc:
        mkdir -p $(toolchain_wrkdir)
        $(MAKE) -C $(linux_srcdir) O=$(toolchain_wrkdir) ARCH=riscv INSTALL_HDR_PATH=$(abspath $(toolchain_srcdir)/linux-headers) headers_install
        cd $(toolchain_wrkdir); $(toolchain_srcdir)/configure \
                --prefix=$(toolchain_dest) \
                --with-arch=$(ISA) \
                --with-abi=$(ABI) 
        $(MAKE) -C $(toolchain_wrkdir) linux
 
编译完毕后，我们就可以在 toolchain/bin 当中看到一系列的 riscv64-unknown-linux-gnu 工具链：
.. code-block:: sh

        riscv64-unknown-linux-gnu-addr2line
        riscv64-unknown-linux-gnu-ar
        riscv64-unknown-linux-gnu-as
        riscv64-unknown-linux-gnu-c++
        riscv64-unknown-linux-gnu-c++filt
        riscv64-unknown-linux-gnu-cpp
        riscv64-unknown-linux-gnu-elfedit
        riscv64-unknown-linux-gnu-g++
        riscv64-unknown-linux-gnu-gcc
        riscv64-unknown-linux-gnu-gcc-13.2.0
        riscv64-unknown-linux-gnu-gcc-ar
        riscv64-unknown-linux-gnu-gcc-nm
        ...


因为网上一般有编译好的 riscv64-linux-gnu 工具链和 riscv64-unknown-linux-gnu 工具链，因此在对工具链没有特殊要求的时候，也可以考虑直接安装。如果对于 abi、isa 有特殊要求，就必须自己编译了。

编译 riscv-unknown-elf-toolchain
--------------------------------

模块的同步、参数的设置和上一节同理。riscv-unknown-elf 工具链也不依赖于 linux，因此我们直接执行 makefile 脚本开始编译即可。

编译的 target 如下：

.. code-block:: Makefile

        target_newlib := riscv64-unknown-elf
        $(RISCV)/bin/$(target_newlib)-gcc:
        mkdir -p $(toolchain_wrkdir)
        cd $(toolchain_wrkdir); $(toolchain_srcdir)/configure \
                --prefix=$(toolchain_dest) \
                --enable-multilib
        $(MAKE) -C $(toolchain_wrkdir)


编译结束后就可以在 toolchain/bin 当中找到 riscv64-unknown-elf 相关的工具链。

buildroot
~~~~~~~~~~~

buildroot 模块被用于构造 initramfs，也就是用于初始化的、被保存在内存中的文件系统。处理器完成 kernel 的初始化之后需要执行用户态程序，进入用户态完成最后的初始化。但是用户态的程序是以文件的形式保存在文件系统中的，而文件系统往往是被存在外部设备中的。为了读入这些外部设备，反过来需要用到文件系统中对于 dev 的管理和外部驱动。为了解决这部分死锁，文件系统的一个子集被作为 initramfs 和 kernel 打包，然后和 kernel 一起被载入内存，这样就可以从内存中启动文件系统的初始化进程了。

等 initramfs 在用户态初始化的过程中会进一步的将其他外部存储中的大型文件系统，比如 debian、ubuntu 等挂载到文件系统中，进行后续的管理和访问。

配置文件
----------

编译 buildroot 需要依赖一个额外的配置文件，这里保存在 conf/buildroot_initramfs_config 当中，文件的配置如下：

.. code-block:: text

        BR2_riscv=y
        BR2_TOOLCHAIN_EXTERNAL=y
        BR2_TOOLCHAIN_EXTERNAL_PATH="$(RISCV)"
        BR2_TOOLCHAIN_EXTERNAL_CUSTOM_PREFIX="riscv64-unknown-linux-gnu"
        BR2_TOOLCHAIN_EXTERNAL_HEADERS_6_4=y
        BR2_TOOLCHAIN_EXTERNAL_CUSTOM_GLIBC=y
        # BR2_TOOLCHAIN_EXTERNAL_INET_RPC is not set
        BR2_TOOLCHAIN_EXTERNAL_CXX=y

BR2_TOOLCHAIN_EXTERNAL_HEADERS_6_4=y 定义了 buildroot 依赖的 linux 内核的版本类型，比如这里是因为我们搭配的 linux 内核是 6.4 版本，如果更换了内核版本，这个参数也要跟着做修改。

开始编译
---------

编译 buildroot 的 makefile 脚本如下：

.. code-block:: Makefile

        buildroot_srcdir := $(srcdir)/buildroot
        buildroot_initramfs_wrkdir := $(topdir)/rootfs/buildroot_initramfs
        buildroot_initramfs_tar := $(buildroot_initramfs_wrkdir)/images/rootfs.tar
        buildroot_initramfs_config := $(confdir)/buildroot_initramfs_config
        buildroot_initramfs_sysroot_stamp := $(wrkdir)/.buildroot_initramfs_sysroot
        buildroot_initramfs_sysroot := $(topdir)/rootfs/buildroot_initramfs_sysroot


- conf/buildroot_initramfs_config：提供的 buildroot 的配置
- repo/buildroot：buildroot 的源代码
- rootfs/buildroot_initramfs：buildroot 编译的工作区
- rootfs/buildroot_initramfs/.config：编译 buildroot 用到的完整的 buildroot 配置
- rootfs/buildroot_initramfs/image/rootfs.tar：buildroot 编译得到的 initramfs 压缩包
- rootfs/buildroot_initramfs_sysroot：rootfs.tar 解压缩后的内容

.. code-block:: Makefile

        $(buildroot_initramfs_wrkdir)/.config: $(buildroot_srcdir)
                rm -rf $(dir $@)
                mkdir -p $(dir $@)
                cp $(buildroot_initramfs_config) $@
                $(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir) olddefconfig CROSS_COMPILE=riscv64-unknown-linux-gnu-

        $(buildroot_initramfs_tar): $(buildroot_srcdir) $(buildroot_initramfs_wrkdir)/.config $(RISCV)/bin/$(target_linux)-gcc $(buildroot_initramfs_config)
                $(MAKE) -C $< RISCV=$(RISCV) PATH="$(PATH)" O=$(buildroot_initramfs_wrkdir)

        $(buildroot_initramfs_sysroot): $(buildroot_initramfs_tar)
                mkdir -p $(buildroot_initramfs_sysroot)
                tar -xpf $< -C $(buildroot_initramfs_sysroot) --exclude ./dev --exclude ./usr/share/locale

        .PHONY: buildroot_initramfs_sysroot
        buildroot_initramfs_sysroot: $(buildroot_initramfs_sysroot)


1. 执行 buildroot_initramfs_sysroot 项目，编译 initramfs 的 sysroot
2. 执行 $(buildroot_initramfs_wrkdir)/.config，该目标将 conf/buildroot_initramfs_config 拷贝到 rootfs/buildroot_initramfs，然后执行 buildroot 的 oldconfig 项目，在 conf/buildroot_initramfs_config 的基础上生成 .config
3. 执行 $(buildroot_initramfs_tar)，根据 .config 的配置，生成文件系统的 tar 压缩包，保存在 rootfs/buildroot_initramfs/images/rootfs.tar
4. 执行 $(buildroot_initramfs_sysroot)，将 rootfs.tar 解压到 rootfs/buildroot_initramfs_sysroot

编译结果
-----------------

我们可以打开 rootfs/buildroot_initramfs_sysroot 来查看对应的文件系统结果：

.. code-block:: sh

        riscv-spike-sdk/rootfs/buildroot_initramfs_sysroot$ ls
        bin  data  etc  lib  lib64  linuxrc  media  mnt  opt  proc  root  run  sbin  sys  tmp  usr  var


执行 ls 命令可以看到，实际上 bin 文件夹下的系统目录只有一个 busybox 是真实存在的应用，其他的 ls、cp 等简单功能都是链接到 busybox，由 busybox 实现。所以这个 initramfs 实际上就是用 busybox 提供功能服务的。

.. code-block:: sh

        rootfs/buildroot_initramfs_sysroot/bin$ ls -l
        total 964
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 arch -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 ash -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 base32 -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 base64 -> busybox
        -rwsr-xr-x 1 zyy zyy 984696 Dec  2  2023 busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 cat -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 chattr -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 chgrp -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 chmod -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 chown -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 cp -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 cpio -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 date -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 dd -> busybox
        lrwxrwxrwx 1 zyy zyy      7 Dec  2  2023 df -> busybox
        ...

initramfs
------------------

conf/initramfs.txt 是 kernel 携带 initramfs 的时候额外需要携带的文件，文件内容如下：

.. code-block:: sh

        dir /dev 755 0 0
        nod /dev/console 644 0 0 c 5 1
        nod /dev/null 644 0 0 c 1 3
        slink /init /bin/busybox 755 0 0

当 initramfs 文件系统被挂载之后，他会执行这个 initramfs.txt 中的命令，生成额外的 dev 文件夹，将 bin/busybox 链接到 init 进程，之后开始执行 init 进程进行用户态的初始化。

追加文件
-------------------

在 initramfs 编译完成后，如果用户需要自己额外提供其他的文件，可以在 rootfs/buildroot_initramfs_sysroot 对应的文件夹中加入额外的文件。因为 sysroot 文件夹的权限是 root 的，所以这个时候需要用 sudo 权限才可以加入文件成功。

linux
~~~~~~~~~~~

linux 内核是操作系统的核心部分，负责初始化系统态的各个程序和提供各类系统调用，然后挂载 initramfs 进行下一阶段的初始化。

配置文件
----------------

编译 linux 同样依赖配置文件 conf/linux_defconfig，该配置文件内容如下：

.. code-block:: text

        CONFIG_EMBEDDED=y
        CONFIG_SOC_SIFIVE=y
        CONFIG_SMP=y
        CONFIG_HZ_100=y
        CONFIG_CMDLINE="earlyprintk"
        CONFIG_PARTITION_ADVANCED=y
        # CONFIG_COMPACTION is not set
        ....


一些比较特殊的配置字段如下：
- CONFIG_DEFAULT_HOSTNAME="riscv-rss"：riscv-rss 是 riscv-spike-sdk 的简称
- CONFIG_BLK_DEV_INITRD=y：表示 initramfs 会被 kernel 打包作为 payload
- CONFIG_HVC_RISCV_SBI=y：允许使用 hvc 功能
- CONFIG_EXT4_FS=y：文件系统格式为 ext4_fs，initramfs 的格式就是对应的 ext4
- CONFIG_MODULES=y：允许加载额外的内核模块，即可以执行 insmod、rmmod 等

开始编译
---------------------

编译 linux 的脚本如下：

.. code-block:: makefile

        linux_srcdir := $(srcdir)/linux
        linux_wrkdir := $(wrkdir)/linux
        linux_defconfig := $(confdir)/linux_defconfig

        vmlinux := $(linux_wrkdir)/vmlinux
        vmlinux_stripped := $(linux_wrkdir)/vmlinux-stripped
        linux_image := $(linux_wrkdir)/arch/riscv/boot/Image

- repo/linux：为 linux 的源代码
- conf/linux_defconfig：为 linux 的默认配置选项
- build/linux：为编译 linux 的工作区域
- build/linux/vmlinux：为 linux 编译得到的 elf 文件
- build/linux/vmlinux-stripped：是 vmlinux 删去符号表等冗余信息之后的文件
- build/linux/arch/riscv/boot/Image：vumlinux-stripped 生成的二进制镜像文件

.. code-block:: sh

        $(linux_wrkdir)/.config: $(linux_defconfig) $(linux_srcdir)
                mkdir -p $(dir $@)
                cp -p $< $@
                $(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- olddefconfig
                echo $(ISA)
                echo $(filter rv32%,$(ISA))
        ifeq (,$(filter rv%c,$(ISA)))
                sed 's/^.-CONFIG_RISCV_ISA_C.-$$/CONFIG_RISCV_ISA_C=n/' -i $@
                $(MAKE) -C $(linux_srcdir) O=$(linux_wrkdir) ARCH=riscv CROSS_COMPILE=riscv64-unknown-linux-gnu- olddefconfig
        endif

        $(vmlinux): $(linux_srcdir) $(linux_wrkdir)/.config $(buildroot_initramfs_sysroot)
                $(MAKE) -C $< O=$(linux_wrkdir) \
                        CONFIG_INITRAMFS_SOURCE="$(confdir)/initramfs.txt $(buildroot_initramfs_sysroot)" \
                        CONFIG_INITRAMFS_ROOT_UID=$(shell id -u) \
                        CONFIG_INITRAMFS_ROOT_GID=$(shell id -g) \
                        CROSS_COMPILE=riscv64-unknown-linux-gnu- \
                        ARCH=riscv \
                        all

        $(vmlinux_stripped): $(vmlinux)
                $(target_linux)-strip -o $@ $<

        $(linux_image): $(vmlinux)

        .PHONY: vmlinux
        vmlinux: $(vmlinux)


1. 执行 $(linux_wrkdir)/.config，将 conf/linux_defconfig 拷贝到 build/linux，然后执行 linux 的 olddefconfig 在 linux_defconfig 的基础上生成新的配置文件 .conf
2. 检查 ISA 是不是包含压缩指令扩展，包含的话新增 CONFIG_RISCV_ISA_C 的配置，重新生成配置文件
3. 执行 $(vmlinux) 将 linux 源码生成 vmlinux 文件和 Image 文件，并将 initramfs_sysroot 打包作为内嵌的文件系统。CONFIG_INITRAMFS_SOURCE 载入对应的 initramfs 的内容，包括 initramfs.txt 和 initramfs_sysroot。
4. 执行 $(vmlinux_stripped) 生成去掉调试信息后的 vmlinux-stripped

riscv-pk
~~~~~~~~~~~~~~~~

riscv-pk 有两个作用，一个是配合 spike 模拟器提供一个简单的 kernel，在这个 kernel 的基础上可以直接运行 riscv 的 elf；
一个是充当简单的 bootloader。riscv-pk 现在已经停止维护了，之后也许我们会用 opensbi 替换 bbl。

开始编译
------------------

.. code-block:: Makefile

        pk_srcdir := $(srcdir)/riscv-pk
        pk_wrkdir := $(wrkdir)/riscv-pk
        bbl := $(pk_wrkdir)/bbl
        pk  := $(pk_wrkdir)/pk


- repo/riscv-pk：riscv-pk 的源代码
- build/riscv-pk：编译 riscv-pk 的工作区
- build/pk：充当模拟器上执行的内核，为 riscv-unknown-elf 编译的程序提供 newlib 的可执行环境
- build/bbl：生成的 bootloader elf 文件，充当系统软件中的 bootloader
- build/bbl.bin：bbl elf 文件对应的二进制镜像

.. code-block:: Makefile

        ifeq ($(BOARD),False)
                DTS=$(abspath conf/spike.dts)
        else
                DTS=$(abspath conf/starship.dts)
        endif

        $(bbl): $(pk_srcdir) $(vmlinux_stripped)
                rm -rf $(pk_wrkdir)
                mkdir -p $(pk_wrkdir)
                cd $(pk_wrkdir) && $</configure \
                        --host=$(target_linux) \
                        --with-payload=$(vmlinux_stripped) \
                        --enable-logo \
                        --with-logo=$(abspath conf/logo.txt) \
                        --with-dts=$(DTS)
                CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir)

        $(pk): $(pk_srcdir) $(RISCV)/bin/$(target_newlib)-gcc
                rm -rf $(pk_wrkdir)
                mkdir -p $(pk_wrkdir)
                cd $(pk_wrkdir) && $</configure \
                        --host=$(target_newlib) \
                        --prefix=$(abspath $(toolchain_dest))
                CFLAGS="-mabi=$(ABI) -march=$(ISA)" $(MAKE) -C $(pk_wrkdir)
                $(MAKE) -C $(pk_wrkdir) install

        .PHONY: bbl
        bbl: $(bbl)


1. DTS 参数用于指定生成 bbl 时候携带的设备树文件，仿真使用 spike.dts，在 VC707 FPGA 环境执行使用 starship.dts
2. 执行 $(bbl) 生成 bbl。先执行 configure，根据 with-dts 选择系统文件携带的系统设备树文件（spike.dts 或者 starship.dts），with-logo 选择系统文件附带的 logo，with-payload 选择负载的 kernel 文件（也就是前面生成的 vmlinux-stripped），host 选择系统文件的编译和运行时环境（riscv64-unknown-linux-gnu 或者 riscv64-unknown-elf）得到对应的配置文件，然后执行 make 生成 pk 和 bbl。
3. 执行 $(pk) 生成 pk。host 选择使用 riscv64-uknown-elf，所以搭配 riscv64-unknown-elf 生成的可执行程序使用；prefix 选择 toolchain，所以生成的程序会被安装到 toolchain 中。

logo
~~~~~~~~~~~~~~~~

我们的 logo 保存在 conf/logo.txt，这个 logo 在 bbl 启动的时候会被打印出来，作为我们的标识符。RSS 是 riscv-spike-sdk 的简写。

.. code-block:: text


                        RISC-V Spike Simulator SDK

                ___           ___           ___     
               /\  \         /\  \         /\  \    
              /  \  \       /  \  \       /  \  \   
             / /\ \  \     / /\ \  \     / /\ \  \  
            /  \~\ \  \   _\ \~\ \  \   _\ \~\ \  \ 
           / /\ \ \ \__\ /\ \ \ \ \__\ /\ \ \ \ \__\
           \/_|  \/ /  / \ \ \ \ \/__/ \ \ \ \ \/__/
              | |  /  /   \ \ \ \__\    \ \ \ \__\  
              | |\/__/     \ \/ /  /     \ \/ /  /  
              | |  |        \  /  /       \  /  /   
               \|__|         \/__/         \/__/ 
     
dts
~~~~~~~~~~~~~~~~~~

程序的正确执行需要软硬件的协同配合，这就要求软件可以知道硬件平台的信息。比如说软件要可以控制串口输出字符信息，那就需要知道串口的产品类型、MMIO 地址，这样才可以调用对应的驱动，读写争取的 MMIO 地址。

如果每个硬件平台的信息都硬编码在软件中，会导致软件需要准备硬件平台定制化。为了保证软件的通用性，这些平台相关的数据被整合为一个设备树文件，由硬件平台厂商提供，存储在平台固件中。当软件启动时，他从平台固件中读取对应的设备树，然后在启动时就可以调用正确的驱动，正确 handle 各个平台硬件了。

此外，也可以让 bootloader 在编译的时候内置平台的设备树，这个设备树会覆盖固件的设备树成为真正的设备树，供后续使用。

- conf/spike.dts：spike 模拟器模拟的硬件平台的设备树，供 spike 模拟器上运行的软件使用
- conf/starship.dts：starship 生成的硬件平台的设备树，供 starship 硬件平台运行的软件使用

spike
~~~~~~~~~~~~~~~~~~

spike 是 riscv 指令集的指令级模拟器。它可以模拟一个多核、简单设备的 RISCV 处理器平台，然后执行 riscv 程序。

开始编译
-------------------

.. code-block:: Makefile

        spike_srcdir := $(srcdir)/riscv-isa-sim
        spike_wrkdir := $(wrkdir)/riscv-isa-sim
        spike := $(toolchain_dest)/bin/spike

- repo/riscv-isa-sim：spike 的源代码
- build/riscv-isa-sim：编译 spike 的工作区
- toolchain/bin/spike：编译后安装的 spike 工具 

.. code-block:: Makefile

        $(spike): $(spike_srcdir)
                rm -rf $(spike_wrkdir)
                mkdir -p $(spike_wrkdir)
                mkdir -p $(dir $@)
                cd $(spike_wrkdir) && $</configure \
                        --prefix=$(dir $(abspath $(dir $@))) 
                $(MAKE) -C $(spike_wrkdir)
                $(MAKE) -C $(spike_wrkdir) install
                touch -c $@

1. prefix 配置指定了生成的 spike 等工具安装的目录位置
2. 在 build/riscv-isa-sim 执行 configure 生成配置文件和 makefile 等，执行 makefile 生成 Spike
3. 执行 make install，将 spike 安装到 toolchain 目录下

安装的结果如下：

.. code-block:: sh

        riscv-spike-sdk/toolchain/bin$ ls | grep spike
        spike
        spike-dasm
        spike-log-parser
        termios-xspike
        xspike

执行简单程序
-------------------------

我们编写一个简单的 riscv 指令集的汇编程序，然后用 riscv64-unknown-elf-gcc 编译为 elf 文件，之后执行**spike testcase.elf**即可在 spike 上执行该程序。

简单程序的执行机理如下，
1. spike 内部会模拟一块 0x10000 开始的 bootrom 和一块 0x80000000 开始的内存
2. 执行 spike testcase.elf 之后，spike 会被 testcase.elf 进行解析，首先 testcase.elf 的起始物理地址（_start 的地址）会被解析出来保存到 0x1000 的内存中，然后 elf 程序中的 program segmentation 会被加载到对应的内存当中
3. 然后 spike 的 PC 初始化为 0x10000，开始执行 bootrom，访问 0x1000 得到起始地址跳入内存，然后开始执行 testcase.elf

spike 还额外模拟了串口等设备，testcase 可以向串口 MMIO 读写来获得外部输入，或者输出字符到 stdout；不然的话 testcase.elf 执行过程中就看不到任何输出。

为了查看 spike 内部执行的情况，或者对 spike 的执行进行断点调试，我们可以执行**spike -d testcase.elf**。-d 选项让 spike 在调试模式下运行，这个时候会有一个交互的命令行供调试者使用。此外对于一个在不断执行的程序们可以执行 ctrl+C 中断程序进入 debug 命令行交互模式。

.. code-block:: sh

        riscv-spike-sdk$ ./toolchain/bin/spike -d starship-dummy-testcase 
        (spike) 
        core   0: 0x0000000000001000 (0x00000297) auipc   t0, 0x0
        (spike)
        core   0: 0x0000000000001004 (0x02028593) addi    a1, t0, 32
        (spike)
        core   0: 0x0000000000001008 (0xf1402573) csrr    a0, mhartid
        (spike) reg 0 t0
        0x0000000000001000
        (spike) reg 0 a1
        0x0000000000001020
        (spike) reg 0 a0
        0x0000000000000000
        (spike)
        core   0: 0x000000000000100c (0x0182b283) ld      t0, 24(t0)
        (spike)
        core   0: 0x0000000000001010 (0x00028067) jr      t0
        (spike) reg 0 t0  
        0x0000000080000000

- 敲击回车可以让 spike 单步执行一条指令
- 可以看到一开始的时候 pc 初始化为 0x10000，执行 bootrom 上的启动程序
- reg core_id reg_name，可以查看寄存器的值。因此 spike 可以模拟多个 core，所以需要 core_id 指示是哪个处理器。
        - reg 0 a0，就是查看 0 号 core 的 a0 寄存器的值。
- 我们解析这部分指令：
        1. a1 获得 0x1020 的地址，这个是处理器固件当中设备树文件所在的地址，这个地址会被传给后续的 bbl、linux 做进一步的解析
        2. t0 读取 0x1000 地址中存储的内容，这个就是 spike 解析 elf 之后存储的 elf 的 entry 的地址
        3. a0 获得 mhartid 的地址，也就是 core 的编号，不同的 core 执行后续的软件时在行为上会存在差异。（比如启动时 0 号 core 负责初始化，其他 core 死循环直到 0 号 core 初始化完毕才继续运行。）
        4. 跳转到 t0 指示的 entry 地址，执行内存中载入的 elf 程序

执行 help 可以查看更多交互命令；如果想退出 spike，执行 q 命令即可：

.. code-block:: sh

        (spike) help
        Interactive commands:
        reg <core> [reg]                # Display [reg] (all if omitted) in <core>
        freg <core> <reg>               # Display float <reg> in <core> as hex
        pc <core>                       # Show current PC in <core>
        priv <core>                     # Show current privilege level in <core>
        mem [core] <hex addr>           # Show contents of virtual memory <hex addr> in [core] (physical memory <hex addr> if omitted)
        str [core] <hex addr>           # Show NUL-terminated C string at virtual address <hex addr> in [core] (physical address <hex addr> if omitted)
        dump                            # Dump physical memory to binary files
        dump_all                        # Dump physical memory to hex and dump regs info to inst
        ...

之后我们继续执行，最后的输出如下：

.. code-block:: sh

        (spike) 
        core   0: 0x00000000800001a0 (0x00000073) ecall
        core   0: exception trap_user_ecall, epc 0x00000000800001a0
        (spike) 
        core   0: >>>>  trap_vector
        core   0: 0x0000000080000004 (0x34202f73) csrr    t5, mcause
        (spike) 
        core   0: 0x0000000080000008 (0x00800f93) li      t6, 8
        (spike) 
        core   0: 0x000000008000000c (0x03ff0863) beq     t5, t6, pc + 48
        (spike)
        core   0: >>>>  write_tohost
        core   0: 0x000000008000003c (0x00001f17) auipc   t5, 0x1
        (spike) 
        core   0: 0x0000000080000040 (0xfc3f2223) sw      gp, -60(t5)

- 对于异常等特殊事件 spike 会给出额外的提示
- spike 会解析 elf 的符号表存储起来，在调试的时候遇到对应的地址会输出对应的符号，作为调试的提示
- 最后可以看到 elf 写了 0x1000 地址之后程序结束，这是 spike 的一个模拟器和主机的 to_host、from_host 交互机制。在一些复杂场景中，spike 是执行在一个 host 程序上的，host 通过 to_host 接口获得 spike 的反馈，通过 from_host 接口向 spike 发送数据和命令。spike 在载入 elf 的时候会查看 elf 有没有定义 to_host 和 from_host 地址，如果定义了这两个地址范围会被用于特殊的 MMIO，spike 上执行的程序通过读写 to_host、from_host 的地址来和 host 交互。在这里，程序向 to_host 写入特殊的值（最低位是 1）来请求退出。

因此 spike 上执行的程序需要满足如下几个特点：
- 需要是 elf 程序
- program segementation 需要有对应的物理地址，这个范围要落在 spike 的物理地址范围中
- elf 如果有 host 交互的需要，需要有 to_host 和 from_host 标号指示的内存区域

newlib 库程序执行
------------------------------

如果我们希望 elf 可以执行更复杂的功能，比如读写 spike 的串口 MMIO 进行 terminal 的输入输出，这个时候就需要在编译的时候链接运行时库。我们可以编写如下的 C 程序，然后用 riscv64-unknown-elf-gcc 编译得到 elf 文件。

.. code-block:: C

        #include<stdio.h>
        int main(){
                printf("hello, world!\n");
        }

这个程序没有办法直接在 spike 上执行：
        - spike 上没有 printf 函数的代码实现
        - elf 没有和物理地址相关的载入说明
但是之前编译的 pk 可以解决这个问题。pk 在 spike 上启动一个小型的操作系统，可以为 elf 提供 newlib 的调用，并且可以将 elf 载入到合适的虚拟地址范围。

因此我们执行 ./toolchain/bin/spike ./build/riscv-pk/pk a.out 就可以在 spike 的 pk 操作系统上执行 a.out 的 elf 程序了。

.. code-block:: sh

        riscv-spike-sdk$ ./toolchain/bin/spike ./build/riscv-pk/pk a.out 
        bbl loader
        hello, world!   

- bbl loader是 pk 成功启动后的输出
- hello, world! 是 a.out 顺利执行后调用 pk 的 newlib 输出的信息

系统软件镜像的运行
-----------------------

1. 首先运行 spike --dum-dts 可以得到 spike 的设备树。conf/spike.dts 就是这样获得的，随着 spike 版本的升级，这个 spike 发生了变化，就可以用同样的方法升级 conf/spike.dts。

.. code-block:: sh

        ./toolchain/bin/spike --dump-dts starship-dummy-testcase
        /dts-v1/;

        / {
        #address-cells = <2>;
        #size-cells = <2>;
        compatible = "ucbbar,spike-bare-dev";
        model = "ucbbar,spike-bare";
        chosen {
        stdout-path = &SERIAL0;
        bootargs = "console=ttyS0 earlycon";
        };
        cpus {
        #address-cells = <1>;
        #size-cells = <0>;
        ...

2. 编译需要的软件，这里直接执行 make bbl 即可，它会依次编译 buildroot、linux kernel、bbl，并且打包 spike.dts，最后得到可执行的 bbl
3. 执行 make sim，也就是 spike bbl 就可以在 spike 上执行我们的系统软件了，会依次启动 bootloader、linux 并挂载 initramfs

.. code-block:: sh

        riscv-spike-sdk$ make sim
        /home/zyy/extend/riscv-spike-sdk/toolchain/bin/spike --isa=rv64imafdc_zifencei_zicsr_zicntr_zihpm /home/zyy/extend/riscv-spike-sdk/build/riscv-pk/bbl
        bbl loader


                        RISC-V Spike Simulator SDK

                ___           ___           ___     
               /\  \         /\  \         /\  \    
              /  \  \       /  \  \       /  \  \   
             / /\ \  \     / /\ \  \     / /\ \  \  
            /  \~\ \  \   _\ \~\ \  \   _\ \~\ \  \ 
           / /\ \ \ \__\ /\ \ \ \ \__\ /\ \ \ \ \__\
           \/_|  \/ /  / \ \ \ \ \/__/ \ \ \ \ \/__/
              | |  /  /   \ \ \ \__\    \ \ \ \__\  
              | |\/__/     \ \/ /  /     \ \/ /  /  
              | |  |        \  /  /       \  /  /   
               \|__|         \/__/         \/__/ 
     


        [    0.000000] Linux version 6.6.2-ga06ca85b22f6 (zyy@zyy-OptiPlex-7060) (riscv64-unknown-linux-gnu-gcc (gc891d8dc2) 13.2.0, GNU ld (GNU Binutils) 2.41) #1 SMP Thu Nov 28 13:44:33 +08 2024
        [    0.000000] Machine model: ucbbar,spike-bare
        [    0.000000] SBI specification v0.1 detected
        [    0.000000] earlycon: sbi0 at I/O port 0x0 (options '')
        [    0.000000] printk: bootconsole [sbi0] enabled
        [    0.000000] efi: UEFI not found.
        ...


        [    0.156925] 10000000.ns16550: ttyS0 at MMIO 0x10000000 (irq = 12, base_baud = 625000) is a 16550A
        [    0.158655] NET: Registered PF_PACKET protocol family
        [    0.164865] clk: Disabling unused clocks
        [    0.167220] Freeing unused kernel image (initmem) memory: 8672K
        [    0.174220] Run /init as init process
        Saving 256 bits of non-creditable seed for next boot
        Starting syslogd: OK
        Starting klogd: OK
        Running sysctl: OK
        Starting network: OK

        Welcome to Buildroot
        buildroot login: root
        root
        # ls
        ls
        rgvlt_test.ko
        #

opensbi
~~~~~~~~~~~~~~~~~~~~~~~~~

opensbi 可以替代 bbl 充当 bootloader，并且 opensbi 现在还在被维护使用，应用范围更广，也许之后会全面切换到 opensbi 上。

开始编译
---------------------------

.. code-block:: Makefile

        opensbi_srcdir := $(srcdir)/opensbi
        opensbi_wrkdir := $(wrkdir)/opensbi
        fw_jump := $(opensbi_wrkdir)/platform/generic/firmware/fw_jump.elf

- repo/opensbi：opensbi 的源代码
- build/opensbi：编译 opensbi 的工作区
- build/opensbi/platform/generic/firmware/fw_jump.elf：opensbi 的编译结果

.. code-block:: Makefile

        $(fw_jump): $(opensbi_srcdir) $(linux_image) $(RISCV)/bin/$(target_linux)-gcc
                rm -rf $(opensbi_wrkdir)
                mkdir -p $(opensbi_wrkdir)
                $(MAKE) -C $(opensbi_srcdir) FW_PAYLOAD_PATH=$(linux_image) PLATFORM=generic O=$(opensbi_wrkdir) CROSS_COMPILE=riscv64-unknown-linux-gnu-

编译 opensbi，并且打包 linux image，最后的结果保存在 fw_jump.elf 当中

模拟执行
----------------------------

spike 模拟执行 make sim BL=opensbi 即可让 spike 执行 fw_jump.elf。

.. code-block:: Makefile
        ifeq ($(BL),opensbi)
        .PHONY: sim
        sim: $(fw_jump) $(spike)
                $(spike) --isa=$(ISA) -p4 --kernel $(linux_image) $(fw_jump)

输出结果如下，除了 bootloader 阶段，后续和 bbl 无明显差异：

.. code-block:: sh

        /home/zyy/extend/riscv-spike-sdk/toolchain/bin/spike --isa=rv64imafdc_zifencei_zicsr -p4 --kernel /home/zyy/extend/riscv-spike-sdk/build/linux/arch/riscv/boot/Image /home/zyy/extend/riscv-spike-sdk/build/opensbi/platform/generic/firmware/fw_jump.elf

        OpenSBI v1.3
           ____                    _____ ____ _____
          / __ \                  / ____|  _ \_   _|
         | |  | |_ __   ___ _ __ | (___ | |_) || |
         | |  | | '_ \ / _ \ '_ \ \___ \|  _ < | |
         | |__| | |_) |  __/ | | |____) | |_) || |_
          \____/| .__/ \___|_| |_|_____/|____/_____|
                | |
                |_|

        Platform Name             : ucbbar,spike-bare
        Platform Features         : medeleg
        Platform HART Count       : 4
        Platform IPI Device       : aclint-mswi
        Platform Timer Device     : aclint-mtimer @ 10000000Hz
        Platform Console Device   : uart8250
        Platform HSM Device       : ---
        Platform PMU Device       : ---
        Platform Reboot Device    : htif
        Platform Shutdown Device  : htif
        Platform Suspend Device   : ---
        Platform CPPC Device      : ---
        Firmware Base             : 0x80000000
        Firmware Size             : 352 KB
        Firmware RW Offset        : 0x40000
        Firmware RW Size          : 96 KB
        Firmware Heap Offset      : 0x4e000
        Firmware Heap Size        : 40 KB (total), 2 KB (reserved), 9 KB (used), 28 KB (free)
        Firmware Scratch Size     : 4096 B (total), 328 B (used), 3768 B (free)
        Runtime SBI Version       : 2.0

        Domain0 Name              : root
        Domain0 Boot HART         : 0
        Domain0 HARTs             : 0*,1*,2*,3*
        Domain0 Region00          : 0x0000000010000000-0x0000000010000fff M: (I,R,W) S/U: (R,W)
        Domain0 Region01          : 0x0000000080040000-0x000000008005ffff M: (R,W) S/U: ()
        Domain0 Region02          : 0x0000000002080000-0x00000000020bffff M: (I,R,W) S/U: ()
        Domain0 Region03          : 0x0000000080000000-0x000000008003ffff M: (R,X) S/U: ()
        Domain0 Region04          : 0x0000000002000000-0x000000000207ffff M: (I,R,W) S/U: ()
        Domain0 Region05          : 0x0000000000000000-0xffffffffffffffff M: () S/U: (R,W,X)
        Domain0 Next Address      : 0x0000000080200000
        Domain0 Next Arg1         : 0x0000000082200000
        Domain0 Next Mode         : S-mode
        Domain0 SysReset          : yes
        Domain0 SysSuspend        : yes

        Boot HART ID              : 0
        Boot HART Domain          : root
        Boot HART Priv Version    : v1.12
        Boot HART Base ISA        : rv64imafdc
        Boot HART ISA Extensions  : none
        Boot HART PMP Count       : 16
        Boot HART PMP Granularity : 4
        Boot HART PMP Address Bits: 54
        Boot HART MHPM Info       : 0 (0x00000000)
        Boot HART MIDELEG         : 0x0000000000000222
        Boot HART MEDELEG         : 0x000000000000b109
        [    0.000000] Linux version 6.6.2-ga06ca85b22f6 (zyy@zyy-OptiPlex-7060) (riscv64-unknown-linux-gnu-gcc (gc891d8dc2) 13.2.0, GNU ld (GNU Binutils) 2.41) #1 SMP Thu Nov 28 13:44:33 +08 2024
        [    0.000000] Machine model: ucbbar,spike-bare
        [    0.000000] SBI specification v2.0 detected
        ...

        [    0.392630] NET: Registered PF_PACKET protocol family
        [    0.398815] clk: Disabling unused clocks
        [    0.401385] Freeing unused kernel image (initmem) memory: 8672K
        [    0.443095] Run /init as init process
        Saving 256 bits of non-creditable seed for next boot
        Starting syslogd: OK
        Starting klogd: OK
        Running sysctl: OK
        Starting network: OK

        Welcome to Buildroot
        buildroot login:


磁盘制作
~~~~~~~~~~~~~~~~~~~~~~~~

spike 执行系统程序的时候，它因为软件模拟的，可以随意的将系统软件复制到内存当中，但是硬件 FPGA 执行的时候并不可以。FPGA 执行的时候，系统软件被存在 SD 卡中，然后 FPGA 上的 core 执行固件代码，将系统文件从 SD 卡读入内存。因此我们需要为 FPGA 制作 SD 卡。

首先我们将 SD 卡插入读卡器，然后将读卡器插入主机，之后我们执行 ls /dev，就可以在 /dev 中看到新的 sd 设备。这里的 sda 是主机自带的磁盘，sda1-sda9 是磁盘的各个分区。sdb 就是我们插入的 SD 卡，sdb1-sdb2 是 SD 卡的各个分区。当然也不一定就是 sdb，也可能是 sdc、sdd。

.. code-block:: sh

        riscv-spike-sdk$ ls /dev | grep sd
        sda
        sda1
        sda2
        sda3
        sda7
        sda8
        sda9
        sdb
        sdb1
        sdb2

现在我们对 sdb 这个 SD 卡进行重新分区，并且对每个分区的格式进行设置。执行的命令如下：

.. code-block:: sh
        sudo sgdisk --clear \
                --new=1:2048:67583  --change-name=1:bootloader --typecode=1:2E54B353-1271-4842-806F-E436D6AF6985 \
                --new=2:264192:     --change-name=2:root       --typecode=2:0FC63DAF-8483-4772-8E79-3D69D8477DE4 \
                /dev/sdb
        sudo dd if=./build/riscv-pk/bbl.bin of=/dev/sdb1 bs=4096
        sudo mke2fs -t ext4 /dev/sdb2

1. sgdisk 指令将 SD 卡化为两个分区，指定各自的大小、磁盘分区名和类型，第一个分区是存放二进制镜像，第二个分区存在挂载的文件系统
2. dd 指令将 bbl 对应的二进制镜像 bbl.bin 写入到 sdb 的第一个分区；之后处理器就回去第一个分区，将这个 bbl.bin 写入内存开始执行
3. mke2fs 指令将磁盘制作为 ext4 文件系统，用于后续挂在 debian 等文件系统

.. code-block:: sh

        riscv-spike-sdk$ sudo sgdisk --clear       --new=1:2048:67583  --change-name=1:bootloader --typecode=1:2E54B353-1271-4842-806F-E436D6AF6985       --new=2:264192:     --change-name=2:root       --typecode=2:0FC63DAF-8483-4772-8E79-3D69D8477DE4       /dev/sdb
        Setting name!
        partNum is 0
        Setting name!
        partNum is 1
        The operation has completed successfully.
        
        riscv-spike-sdk$ sudo dd if=./build/riscv-pk/bbl.bin of=/dev/sdb1 bs=4096
        4361+1 records in
        4361+1 records out
        17865344 bytes (18 MB, 17 MiB) copied, 0.747458 s, 23.9 MB/s

        riscv-spike-sdk$ sudo mke2fs -t ext4 /dev/sdb2
        mke2fs 1.46.5 (30-Dec-2021)
        /dev/sdb2 contains a ext4 filesystem
                last mounted on /media/zyy/44290a65-fcf7-4bb6-ba14-e87c91385457 on Fri Nov 29 15:38:19 2024  
        Proceed anyway? (y/N) y
        Creating filesystem with 7758715 4k blocks and 1941504 inodes
        Filesystem UUID: e1729867-d289-4d9c-9a82-df311ebd409e
        Superblock backups stored on blocks:
                32768, 98304, 163840, 229376, 294912, 819200, 884736, 1605632, 2654208,
                4096000

        Allocating group tables: done
        Writing inode tables: done
        Creating journal (32768 blocks):
        done
        Writing superblocks and filesystem accounting information: done

如果要在第二个分区挂载文件系统的话，需要两步操作：

1. 在设备树的 bootargs 中加入 root=/dev/mmcblk0p2，说明根文件系统是在 mmcblk0p2 这个分区的，那么等 linux 启动之后就会根据 root 将 SD 卡第二个分区的文件系统读出来作为根文件系统。
2. sudo mount /dev/sdb2 tmp，将 sd 卡第二个分区挂载在 tmp 文件夹上，然后将其他文件系统的内容拷贝到这个文件夹，之后 umount 挂在即可。

