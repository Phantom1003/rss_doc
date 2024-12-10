sycuricon( 五 ): 指令扩展
==================================================================

本章节我们以 regvault 指令扩展为例介绍如何在 rocket-chip 中增加自己的指令扩展。

regvault
~~~~~~~~~~~~~~~~~~~~~~~~

regvault 是一种细粒度的 selective 数据随机化保护方案，通过有选择对数据进行加密，防止被泄露和篡改。该工作通过对 rocket-chip 处理器扩展 CSR 和指令来实现该功能，更多细节参见论文 `regvault`_。

.. _regvault: https://wenboshen.org/publications/papers/regvault-dac22.pdf

CSR 寄存器扩展
----------------------

regvault 扩展了 16 个用于存储密钥的 key 特权寄存器，两个寄存器 keyl、keyh 组成一个完整的 128 位的密钥。其中一组密钥的特权态是 M 态，一般用于 S 态的加密；七组密钥的特权态是 S 态，一般用于 U 态的加密。CSR 寄存器序号编码如下：

+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
|   CSR     |   number  |   CSR     |   number  |   CSR     |   number  |   CSR     |   number  |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
| mcrmkeyl  |   0x7f0   | mcrmkeyh  |   0x7f1   | scrtkeyl  |   0x5f0   | scrtkeyh  |   0x5f1   |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
| scrakeyl  |   0x5f2   | scrakeyh  |   0x5f3   | scrbkeyl  |   0x5f4   | scrbkeyh  |   0x5f5   |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
| scrckeyl  |   0x5f6   | scrckeyh  |   0x5f7   | scrdkeyl  |   0x5f8   | scrdkeyh  |   0x5f9   |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+
| screkeyl  |   0x5fa   | screkeyh  |   0x5fb   | scrfkeyl  |   0x5fc   | scrfkeyh  |   0x5fd   |
+-----------+-----------+-----------+-----------+-----------+-----------+-----------+-----------+

CSR 寄存器编号的高 9-10 位标识寄存器的特权态：7f0 对应的是 11，所以是 M 态；5f0 对应的是 01，所以是 S 态。其次 xF0-xFF 是处理器预留的 read/write custom 寄存器，暗示了这些寄存器可读可写。

指令扩展
--------------------

regvault 扩展了寄存器加解密指令 crexk、crdxk，指令格式如下：
    
* 加密指令：cre[x]k rd, rs[e:s], rt

  * 功能：选择 crxkeyh:crxkeyl 作为加密密钥，将 rs 寄存器的 (e+1)\*8-1 到 s\*8 位以外的位 mask 为 0 作为待加密数据，将 rt 寄存器的值作为 tweat，然后用 QARMA64 加密算法加密，最后的保存到 rd 寄存器中。  
  * 编码：
    
    * R 型指令，opcode 为 0x6b，FUNCT7 的 0 位是 1
    * x 是用于加密的 key 寄存器标识，f范围是 0-7，对应 m、t、a、b、c、d、e、f，对应 FUNCT3
    * rs 被加密的源数据寄存器，可以只对 rs 中的一部分数据做加密，对应 R 指令中的 RS1 field
    * e 是 rs 中数据加密的上界，范围是 0-7，对应 0、8、16 …… 56 等 8 的倍数，对应 FUNCT7 的 4-6 位
    * s 是 rs 中数据加密的下界，范围是 0-7，对应 7、15 …… 63 等 8 的倍数减 1，对应 FUNCT7 的 1-3 位
    * rt 为加密算法提供 tweak，用于增加加密算法的熵值，对应 R 指令中的 RS2 field
    * rd 保存加密算法计算结果的目标寄存器，对应 R 指令中的 RD field

* 解密指令：crd[x]k rd, rs, rt, [e:s]

  * 功能：选择 crxkeyh:crxkeyl 作为解密密钥，将 rs 寄存器的值作为待解密数据，将 rt 寄存器的值作为 tweat，然后用 QARMA64 加密算法解密，最后的保存到 rd 寄存器中，要求 (e+1)\*8-1 到 s\*8 位以外的位都是 0，不然触发异常
  * 编码：

    * R 型指令，opcode 为 0x6b，FUNCT7 的 0 位是 0
    * x 是用于解密的 key 寄存器标识，f范围是 0-7，对应 m、t、a、b、c、d、e、f，对应 FUNCT3
    * rs 被解密的源数据寄存器，对应 R 指令中的 RS1 field
    * e 是解密后数据的上界，范围是 0-7，对应 0、8、16 …… 56 等 8 的倍数，对应 FUNCT7 的 4-6 位
    * s 是解密后数据的下界，范围是 0-7，对应 7、15 …… 63 等 8 的倍数减 1，对应 FUNCT7 的 1-3 位
    * rt 为解密算法提供 tweak，对应 R 指令中的 RS2 field
    * rd 保存解密算法计算结果的目标寄存器，对应 R 指令中的 RD field

加解密指令的 x、e、s、rt 的值必须完全一致才可以加解密正确，并且解密后 rd[e:s] 以外的值必须是 0 才和 rs[e:s] 加密前的 mask 相对应，一个小型的 demo 如下：

.. code-block:: asm

    # encrypt
    li t1, 0x0987654321098765
    li t0, 0x1234
    scretk t2, t1[5:3], t0

    # decrypt
    scrdtk t1, t2, t0, [5:3]
    li t2, 0x0000654321000000
    bne t1, t2, fail
    j pass

模拟器的 custom 扩展
~~~~~~~~~~~~~~~~~~~~~~~~~~~

我们的目的是在硬件上进行硬件模块的扩展，但我们需要额外的差分验证模块可以验证硬件的正确性，因此我们需要模拟器也可以支持 custom 指令。此外，我们后续也需要设计实现支持 custom 指令扩展的软件和操作系统，在验证软件正确性的时候也需要模拟器的支持。

模拟器的修改代码我们保存在 riscv-spike-sdk 的 regvault 分支的 conf/spike.patch.1，我们将 repo/riscv-isa-sim 子模块下载下来之后，将这个 patch apply 在 riscv-isa-sim 上，然后就可以编译得到支持 revault custom 指令的 spike。现在我们来介绍如何对 spike 的源代码进行修改。

指令集编码扩展
---------------------------

在 riscv/encodeing.h 中增加 key 寄存器对应的各类指令集编码，包括 csr 编码、指令编码等。

下述为csr index 编码宏，便于后续 csr 读写指令寻址 csr 寄存器使用，下面的十六个宏对应十六个 key 寄存器的编号。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 192-207
	:caption: 增加 CSR 编号宏定义

增加 CSR 寄存器单元和对应的 csr 编码之间的对应关系。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 264-279
	:caption: 增加 CSR 寄存器和编号的对应关系

增加 crexk、crdxk 指令的编码。如 opcode、funct3、funct7 的编码。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 152-155
	:caption: 增加 crexk、crdxk 的编码

CSR 寄存器扩展
-----------------------

首先在 csr.h 和 csr.cc 中新增 regvault key csr 相关的类，使得模拟器可以构造 key 寄存器。

在 spike 中每个 CSR 的类都是 csr_t 的子类，该函数提供三个虚函数接口：

* csr_t(processor_t* const proc, const reg_t addr, const reg_t init)：寄存器的初始化接口，proc 是寄存器所在的处理器，addr 是寄存器的 csr index，init 是寄存器的初始值
* reg_t read()：寄存器的读接口，返回寄存器的值
* unlogged_write(const reg_t val)：寄存器的写接口，写入寄存器的值

我们通过继承 csr_t 构造 key csr 的类 key_csr_t，然后重写上述上个虚函数接口，实现定制化的初始化、读、写。不过因为 key 寄存器功能非常简单，所以其实覆写实现也很简单。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 22-43
	:caption: 增加 key csr 的声明

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 3-18
	:caption: 增加 key csr 的定义

之后我们在处理器中实例化这些寄存器，修改 riscv/processor.h 中的 starst_t，定义对应的寄存器变量：

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 496-517
	:caption: 在 state_t 增加 key 寄存器

最后我们在 processor.cc 中的 csrmap 散列表注册对应的寄存器，这样之后执行 csr 读写指令的时候就可以根据 csr 的标号快速定位要处理的 csr 寄存器。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 468-489
	:caption: 根据 csr 编号快速访问 csr

crexk、crdxk 指令扩展
---------------------------------

指令执行首先需要对指令进行译码，因为 crexk、crdxk 指令编码在 R 指令的基础上暗含了对 e、s、x 的编码，所以解码的时候需要额外的支持。

修改 riscv/decode.h 的 insn_t 的类，对指令编码的解码函数进行扩展，便于快速的获得 e、s、x 对应的 field。这里增加了 rgvlt_startb 和 rgvlt_endb 函数来获得 e、s 的 bit。

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 46-53
	:caption: 增加译码支持

然后是指令功能的实现部分。这里并不是给每个指令都实现一个函数，每个函数实现的主体部分被定义在 riscv/insn 文件夹下对应的 h 中。我们可以看一下 crexk 的实现：

* 通过 insn 的函数得到对应的 x、s、e 字段
* 通过 p->set_csr 得到对应的 keyl、keyh
* 通过 RS1、RS2 得到 源寄存器的值
* 数据准备好后调用 qarma64_enc 函数进行加密
* 最后用 WRITE_RD 函数将 计算结果写回 RD
* qarma64_enc 的具体实现参见对应的函数实现

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 306-385
	:caption: crexk 的实现

crxdk 的实现类似，只不过多了一些校验过程。

之后在 riscv/encoding 对 crexk、crdxk 分别定义了一个 DECLARE_INSN 宏，这个宏会构造函数的主体并且 include 这里的头文件得到最后的函数体：

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 233-234
	:caption: 增加 crexk、crdxk 的函数实现

编译文件的注册
------------------------------

因为我们新增了 qarma.h 头文件和 qarma.cc 文件，并且加入了 crexk、crdxk 的指令实现头文件。为了让编译的时候可以对这些 C 文件进行编译链接，对头文件进行包含，需要对负责编译的 riscv.mk.in 进行修改。

* 修改 riscv_install_hdrs 可以加入新的头文件
* 修改 riscv_srcs 可以加入新的源文件
* 修改 riscv_insn_ext_i 可以加入新的指令构造

.. remotecode:: ../_static/tmp/regvault_spike_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/conf/spike.patch.1
	:language: text
	:type: github-permalink
	:lines: 875-899
	:caption: 增加对新增文件的编译

软件的 custom 指令实现
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

我们需要让汇编器可以编译 custom 指令的软件，但是汇编器并不支持 crexk、crdxk 指令和 key 寄存器的速记符。

对于 custom csr 的读写可以直接使用 csr 的编号来代替具体的 csr 寄存器速记符。比如 mcrmkeyl 的寄存器编号是 0x7f0，虽然编译器不能直接识别 ``csrw mcrmkeyl, t0`` 这样的指令，但是可以汇编指令 ``csrw 0x7f0, t0``。

对于 crexk、crdxk 等指令，则可以使用汇编器提供的 insn r 的接口。因为 crexk 是 R 型指令，我们可以用 ``insn r`` 告诉汇编器这是我们自定义的 R 型汇编指令，对于指令的各个 field 的二进制则使用硬编码的方式予以补齐。例如 ``.insn r 0x6b, 0x0, 0x55, t2, t0, t1``，就是说明指令的 opcode 是 0x6b、funct3 是 0x0、funct7 是 0x55， 对应的 crexk、crdxk 指令为 ``crdtk t2, t0, t1, [5:2]``。

除了用 insn r 之外也可以直接用 .word 对指令进行硬编码，只不过可读性会很差，指令最好是用编程脚本自动化生成，而不是人工编写；如果想要兼顾可读性和编码能力，也可以定义宏，通过接受参数转化为对应的 insn r。

我们在 starship 的 regvault 分支中新建了 test 文件夹，来自动化生成 regvault 指令扩展的测试脚本，包括三个子部分：

* function_test：人工设计了一系列的测试模块，对 key 寄存器的读写、不同 tweak 的数据加密解密、不同 mask 区域的数据加密解密、不同 key 寄存器的数据加密解密进行较完整的测试
* pressure_test：自动化生成上万个随机的 key 寄存器读写、数据加解密指令，然后对处理器进行压力测试
* effect_test：根据一些调用规则对寄存器计算、加密、解密等顺序进行限定，使得加解密数据的形式和真实的 C 函数数据加解密的形式近似，从而近似测量 CLB 缓存的命中率。理论上在的期望是 50%。

硬件的 custom 指令的实现
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为了让 rocket-chip 处理器可以支持 regvault 指令扩展，我们需要对 rocket-chip 进行修改。这部分修改我们保存在 starship 的 regvault 分支的 patch/regvault 文件夹下，切换到 regvault 分支之后，将这个 patch 应用到 repo/rocket-chip 即可。

rocket-chip 为 custom 提供了 RoCC 实现机制。RoCC 类似一个协处理器，当 rocket-chip 译码 custom inst 的时候就会把它发送给 RoCC 执行，然后 scoreboard 等待 RoCC 执行完毕，接受来自 RoCC 的返回值，并提交指令。

现在我们来介绍如何对 Rocket-chip 的硬件代码进行修改，包括加解密的硬件实现、custom CSR 寄存器的注册、译码模块的调整、RoCC 接口的调用等等。

LazyModule 和 Diplomacy
--------------------------

chisel 提供了一种 LazyModule 和 Diplomacy 机制。对于一个模块有时候是需要参数化配置的，常见的做法就是将所有参数都从顶层模块确定，然后不断传递给子模块，同时实例化各个子模块。但是有时候子模块之间也需要参数的传递和通讯，这个时候 LazyModule 和 Diplomacy 就可以起到作用。

例如说 custom csr 的生成和 CSR 模块和 RoCC 模块有关，CSR 是 custom csr 的提供方，RoCC 是 custom csr 的需求方，而这需要对 custom csr 的生成进行协作。传统的方法是在模块的顶层提供 custom csr 的参数，然后从顶层分别传递给 CSR 和 RoCC，确保二者的配置保持一致。但是这会导致所有的参数都集中到顶层，编程者需要人工管理所有的顶层参数，没有很好局部化的设计（虽然也不是不行）。

LazyModule 和 Diplomacy 机制解决了上述问题。首先如果一个模块的参数不能在一开始被确定，那么就用 LazyModule 而不是 Module 来实现它，LazyModule 可以在内部定义和向外部的模块提供参数，Diplomacy 机制则可以让参数在模块之间相互传播。我们让 RoCC 用 LazyModule 实现，并且在内部定义 custom csr 的参数，这些参数会被 diplomacy 机制传递到模块顶层，然后下传到 CSR 模块，从而让两者可以有一样的参数。这样我们只需要在 RoCC 内部解决这个参数定义问题，这样确保了参数的局部性，在定义和修改一个新参数的时候，只要关注参数的提供方和使用方即可，而不需要在乎中间的传递过程以及和其它参数的冲突问题。

LazyModule 实际上只负责做模块的参数传递，通过 Diplomacy 让模块之间进行参数的协定，而模块的硬件实现需要多有一个 LazyModuleImp 来实现。LazyModule 在做完参数传递确定参数之后，调用 LazyModuleImp 来实现最后的硬件设计。

RoCC 加解密模块的实现
-----------------------------

我们用 RoCC 机制实现 crexk、crdxk 指令，在 repo/rocket-chip/src/main/scala/rocc 新建 PointerEncryption.scala。

PointerEncryption 模块继承 LazyRoCC，来作为加解密引擎 RoCC 的参数传递：

* RoCC 会为 CSR 模块提供 roccCSRs，数据类型为 Seq[CustomCSR]，用于向 CSR 传递每个 CustomCSR 的属性，参见 LazyRoCC 的参数定义和 CustomCSR 类定义
* RoCC 为 RoCCImp 提供一个额外的 nRoCCCSRs 参数，传递 CustomCSR 的个数
* 调用 PointerEncryptionMultiCycleImp 实现 PointerEncryption 的实际电路部分

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 5-39
	:caption: PointerEncryption

PointerEncryptionMultiCycleImp 是 PointerEncryption 的硬件实现，负责接受来自 PointerEncryption 的参数，实现对应的电路。

* PointerEncryptionMultiCycleImp 下辖两个子模块（内部模块连接）
    
  * pec_engine 是 QarmaMultiCycle 模块，负责对输入的数据、tweak、key 进行加密解密
  * cache 是 QarmaCache 模块，负责缓存数据加密解密的对应的结果，便于加密数据的快速解密

* PointerEncryptionImp 包含两组输入输出接口（外部模块连接）

  * 一组是 RoCC 和 Pipeline 之间的输入输出，负责接收 custom inst 请求，返回对应的结果，参见 RoCCIO 和 RoCCCoreIO 类。
  * 一组是 RoCC 和 CSR 之间的输入输出，负责 CustomCSR 之间的数据传输，参见 CustomCSRs.scala 的 CustomCSRIO 类。

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 131-136
	:caption: PointerEncryptionMultiCycleImp

加解密模块的各个子模块我们编写在 repo/rocket-chip/src/main/scala/rocc 的 PointerEncryption.scala 和 QARMA.scala，我们做一个简单的罗列。具体实现可以自行阅读。

* PointerEncryption.scala

  * PointerEncryption：加解密 RoCC 的 LazyRoCC
  * PointerEncryptionSingleCycleImp：单周期的加解密 RoCC 的模块实现
  * PointerEncryptionMultiCycleImp：多周期的加解密 RoCC 的模块实现

* QARMA.scala

  * QarmaParams：定义 QARMA 算法的各个参数
  * MixColumnOperator：执行 QARMA 的 MixColumn 阶段
  * ForwardTweakUpdateOperator：执行 QARMA 的 Forward Tweak 更新
  * BackwardTweakUpdateOperator：执行 QARMA 的 Backward Tweak 更新
  * ForwardOperator：执行 QARMA 的 Forward 阶段
  * BackwardOperator：执行 QARMA 的 Backward 阶段
  * PseudoReflectOperator：执行 QARMA 的 PseudoReflect 阶段
  * QarmaSingleCycle：单周期的 QARMA 算法
  * QarmaMultiCycle：多周期的 QARMA 算法，参数 max_round 是加解密的最大轮数，参数 stage_round 是每个周期加解密的轮数
  * QarmaCache：QARMA 算法的缓存，参数 depth 为缓存的深度，参数 policy 为缓存的策略

CustomCSR 的调整
-------------------------------

因为 RoCC 的使用，我们需要对 CSRFile 做一些调整：

* 因为 RoCC 被启用，所以 io_dec.rocc_illegal 被设置为 false，这样执行 RoCC 指令的时候就不会被触发异常；其实将 x 扩展打开会更符合指令集手册规定一些
* writeCustomCSR 中的 mask 修改为全 1，因为 Key 寄存器的所有位都可以被直接修改；理论上应该从 csr.mask 参数传递，但是 csr.mask 似乎不能设置 64 位的整数，就只能这样简单解决了
* setCustomCSR 对 mask 的修改和 writeCustomCSR 同理

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 937-965
	:caption: CustomCSR 读写行为调整

对于早期的 Rocket-chip 有一个需要调整的 bug，但是在后期的 Rocket-chip 中已经修复了。rocc 的 csrs 既有输入也有输出，所以在和 roccCSRIOs 链接的时候需要用 ``<>`` 而不是简单的 ``:=`` 符号。  

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 1082-1089
	:caption: CustomCSR 连接 bug 修复

扩展指令的调整
--------------------------

我们需要在 CustomInstructions 模块中加入我们自定义的 PECInst 指令的编码，告诉 Rocket-chip 我们定义了这个指令。

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 968-975
	:caption: rocc 增加 regvault custom 指令

之后我们在 IDecode 模块中加入 PECInst 指令的译码表，这里用和其他的 R 型指令 RoCC 一样的译码信号就可以了。

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 988-997
	:caption: 增加 regvault 指令译码

对于 RoCC 支持的 OpcodeSet 进行扩展，增加 regvault 扩展指令对应的 opcode set

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 1068-1077
	:caption: 扩展 OpcodeSet

处理器生成的配置调整
--------------------------

现在虽然我们的译码模块可以支持 regvault 指令，并且定义了 regvault 指令的 RoCC 模块，但是还需要再配置中增加 RoCC 的生成配置，不然生成处理器不会实例化 regvault 相关的部件。

在 subsystem/Config.scala 中定义配置 WithPECRoCC。该模块会让 BuildRoCC 这个参数的值变为实例化的 pec_engine。

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 1036-1043
	:caption: 增加 rocc 实例化配置

之后我们对 repo/starship 中的配置进行修改，为 StarshipBaseConfig 增加 ``new WithPECRocc ++``。
这样实例化 starship 的 RoCC 的时候就会生成 pec_engine，并且做模块间的连接。

其他调整
---------------------

为了让处理器可以匹配比较新的内核版本，需要支持 5 级页表，而不是 3 级页表，我们对 subsystem/Configs.scala 做修改，将 PgLevels 的值从 3 改为 5。

.. remotecode:: ../_static/tmp/regvault_starship_patch
	:url: https://github.com/sycuricon/starship/blob/a36a8eedeeafb4e377583e70594499a28cccb9bb/patch/regvault/1.patch
	:language: text
	:type: github-permalink
	:lines: 1021-1029
	:caption: 修改为 5 级页表

之后我们执行 ``make vlt`` 或者 ``make bitstream`` 就可以得到有 regvault 指令扩展的程序了。

RoCC 的实现存在两个局限性：

* CSR 的修改和 RoCC 的执行是分离的，所以在 RoCC 执行的过程中 CSR 被修改会影响 RoCC。所以在软件设计的时候，请不要将 CSR 的修改和加解密放在一起执行，中间请用 fence.i 隔开。
* RoCC 无法触发异常，这样解密的时候发现解密结果错误，没有办法触发异常，需要后续额外的软件检查加以弥补。

扩展指令的验证
~~~~~~~~~~~~~~~~~~~~~~~~~

我们现在实现了模拟器的指令扩展、扩展指令测试程序的生成和硬件的指令扩展。我们先假设模拟器的实现和测试程序的生成是正确的（实际上不一定），然后验证处理器的正确性。

我们首先用 starship regvault 分支的 effect_test 和 pressure_test 生成足够多的测试样例，然后执行 ``make vlt STARSHIP=xxx`` 进行差分测试即可。

下板执行的时候，因为 key 寄存器只能在 S 态、M 态进行修改，我们可以用一个简单 kernel module 来解决这个问题。我们在 riscv-spike-sdk 的 regvault 分支实现了一个 regvault kernel module，在初始化函数中加入对 key 寄存器的修改，和对数据的加密解密。通过比对输出的加解密结果是否正确，从而检查下板之后加解密模块是否正确。

.. remotecode:: ../_static/tmp/regvault_kernel_module
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/82c596f4854ae3d6a8fe66d764e9125d2e374e44/test/rgvlt_test.c
	:language: C
	:type: github-permalink
	:lines: 27-84
	:caption: 测试 regvault 的内核模块
