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

.. code-block:: text

	+#define CSR_MCRMKEYL 0x7f0
	+#define CSR_MCRMKEYH 0x7f1
	+#define CSR_SCRTKEYL 0x5f0
	+#define CSR_SCRTKEYH 0x5f1
	+#define CSR_SCRAKEYL 0x5f2
	+#define CSR_SCRAKEYH 0x5f3
	+#define CSR_SCRBKEYL 0x5f4
	+#define CSR_SCRBKEYH 0x5f5
	+#define CSR_SCRCKEYL 0x5f6
	+#define CSR_SCRCKEYH 0x5f7
	+#define CSR_SCRDKEYL 0x5f8
	+#define CSR_SCRDKEYH 0x5f9
	+#define CSR_SCREKEYL 0x5fa
	+#define CSR_SCREKEYH 0x5fb
	+#define CSR_SCRFKEYL 0x5fc
	+#define CSR_SCRFKEYH 0x5fd

增加 CSR 寄存器单元和对应的 csr 编码之间的对应关系。

.. code-block:: text

	+DECLARE_CSR(mcrmkeyl, CSR_MCRMKEYL)
	+DECLARE_CSR(mcrmkeyh, CSR_MCRMKEYH)
	+DECLARE_CSR(scrtkeyl, CSR_SCRTKEYL)
	+DECLARE_CSR(scrtkeyh, CSR_SCRTKEYH)
	+DECLARE_CSR(scrakeyl, CSR_SCRAKEYL)
	+DECLARE_CSR(scrakeyh, CSR_SCRAKEYH)
	+DECLARE_CSR(scrbkeyl, CSR_SCRBKEYL)
	+DECLARE_CSR(scrbkeyh, CSR_SCRBKEYH)
	+DECLARE_CSR(scrckeyl, CSR_SCRCKEYL)
	+DECLARE_CSR(scrckeyh, CSR_SCRCKEYH)
	+DECLARE_CSR(scrdkeyl, CSR_SCRDKEYL)
	+DECLARE_CSR(scrdkeyh, CSR_SCRDKEYH)
	+DECLARE_CSR(screkeyl, CSR_SCREKEYL)
	+DECLARE_CSR(screkeyh, CSR_SCREKEYH)
	+DECLARE_CSR(scrfkeyl, CSR_SCRFKEYL)
	+DECLARE_CSR(scrfkeyh, CSR_SCRFKEYH)

增加 crexk、crdxk 指令的编码。如 opcode、funct3、funct7 的编码。

.. code-block:: text

	+#define MATCH_CRDXK 0x200006b
	+#define MASK_CRDXK 0x200007f
	+#define MATCH_CREXK 0x6b
	+#define MASK_CREXK 0x200007f

	+DECLARE_INSN(crdxk, MATCH_CRDXK, MASK_CRDXK)
	+DECLARE_INSN(crexk, MATCH_CREXK, MASK_CREXK)

CSR 寄存器扩展
-----------------------

首先在 csr.h 和 csr.cc 中新增 regvault key csr 相关的类，使得模拟器可以构造 key 寄存器。

在 spike 中每个 CSR 的类都是 csr_t 的子类，该函数提供三个虚函数接口：

* csr_t(processor_t* const proc, const reg_t addr, const reg_t init)：寄存器的初始化接口，proc 是寄存器所在的处理器，addr 是寄存器的 csr index，init 是寄存器的初始值
* reg_t read()：寄存器的读接口，返回寄存器的值
* unlogged_write(const reg_t val)：寄存器的写接口，写入寄存器的值

我们通过继承 csr_t 构造 key csr 的类 key_csr_t，然后重写上述上个虚函数接口，实现定制化的初始化、读、写。不过因为 key 寄存器功能非常简单，所以其实覆写实现也很简单。

.. code-block:: text

	--- a/riscv/csrs.h
	+++ b/riscv/csrs.h
	@@ -843,4 +843,19 @@ class smcntrpmf_csr_t : public masked_csr_t {
			private:
			std::optional<reg_t> prev_val;
	};
	+
	+class key_csr_t: public csr_t {
	+ public:
	+  key_csr_t(processor_t* const proc, const reg_t addr, const reg_t init);
	+
	+  virtual reg_t read() const noexcept override {
	+    return val;
	+  }
	+
	+ protected:
	+  virtual bool unlogged_write(const reg_t val) noexcept override;
	+ private:
	+  reg_t val;
	+};
	+
	#endif

	--- a/riscv/csrs.cc
	+++ b/riscv/csrs.cc
	@@ -1692,3 +1692,13 @@ bool smcntrpmf_csr_t::unlogged_write(const reg_t val) noexcept {
			prev_val = read();
			return masked_csr_t::unlogged_write(val);
	}
	+
	+key_csr_t::key_csr_t(processor_t* const proc, const reg_t addr, const reg_t init):    
	+  csr_t(proc, addr),
	+  val(init) {
	+}
	+
	+bool key_csr_t::unlogged_write(const reg_t val) noexcept {
	+  this->val = val;
	+  return true;
	+}

之后我们在处理器中实例化这些寄存器，修改 riscv/processor.h 中的 starst_t，定义对应的寄存器变量：

.. code-block:: text

	--- a/riscv/processor.h
	+++ b/riscv/processor.h
	@@ -111,6 +111,22 @@ struct state_t
	csr_t_p stvec;
	virtualized_csr_t_p satp;
	csr_t_p scause;
	+  csr_t_p mcrmkeyh;
	+  csr_t_p mcrmkeyl;
	+  csr_t_p scrakeyh;
	+  csr_t_p scrakeyl;
	+  csr_t_p scrbkeyh;
	+  csr_t_p scrbkeyl;
	+  csr_t_p scrckeyh;
	+  csr_t_p scrckeyl;
	+  csr_t_p scrdkeyh;
	+  csr_t_p scrdkeyl;
	+  csr_t_p screkeyh;
	+  csr_t_p screkeyl;
	+  csr_t_p scrfkeyh;
	+  csr_t_p scrfkeyl;
	+  csr_t_p scrtkeyh;
	+  csr_t_p scrtkeyl;

最后我们在 processor.cc 中的 csrmap 散列表注册对应的寄存器，这样之后执行 csr 读写指令的时候就可以根据 csr 的标号快速定位要处理的 csr 寄存器。

.. code-block:: text

	--- a/riscv/processor.cc
	+++ b/riscv/processor.cc
	@@ -585,6 +585,23 @@ void state_t::reset(processor_t* const proc, reg_t max_isa)
			}
	}

	+  csrmap[CSR_MCRMKEYH] = std::make_shared<key_csr_t>(proc, CSR_MCRMKEYH, 0);
	+  csrmap[CSR_MCRMKEYL] = std::make_shared<key_csr_t>(proc, CSR_MCRMKEYL, 0);
	+  csrmap[CSR_SCRAKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRAKEYH, 0);
	+  csrmap[CSR_SCRAKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRAKEYL, 0);
	+  csrmap[CSR_SCRBKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRBKEYH, 0);
	+  csrmap[CSR_SCRBKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRBKEYL, 0);
	+  csrmap[CSR_SCRCKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRCKEYH, 0);
	+  csrmap[CSR_SCRCKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRCKEYL, 0);
	+  csrmap[CSR_SCRDKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRDKEYH, 0);
	+  csrmap[CSR_SCRDKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRDKEYL, 0);
	+  csrmap[CSR_SCREKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCREKEYH, 0);
	+  csrmap[CSR_SCREKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCREKEYL, 0);
	+  csrmap[CSR_SCRFKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRFKEYH, 0);
	+  csrmap[CSR_SCRFKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRFKEYL, 0);
	+  csrmap[CSR_SCRTKEYH] = std::make_shared<key_csr_t>(proc, CSR_SCRTKEYH, 0);
	+  csrmap[CSR_SCRTKEYL] = std::make_shared<key_csr_t>(proc, CSR_SCRTKEYL, 0);

crexk、crdxk 指令扩展
---------------------------------

指令执行首先需要对指令进行译码，因为 crexk、crdxk 指令编码在 R 指令的基础上暗含了对 e、s、x 的编码，所以解码的时候需要额外的支持。

修改 riscv/decode.h 的 insn_t 的类，对指令编码的解码函数进行扩展，便于快速的获得 e、s、x 对应的 field。这里增加了 rgvlt_startb 和 rgvlt_endb 函数来获得 e、s 的 bit。

.. code-block:: text

	diff --git a/riscv/decode.h b/riscv/decode.h
	index cd1c0a1..0e05b2b 100644
	--- a/riscv/decode.h
	+++ b/riscv/decode.h
	@@ -93,6 +93,8 @@ public:
			uint64_t iorw() { return x(20, 8); }
			uint64_t bs() { return x(30, 2); } // Crypto ISE - SM4/AES32 byte select.
			uint64_t rcon() { return x(20, 4); } // Crypto ISE - AES64 round const.
	+  uint64_t rgvlt_startb() { return x(26, 3); }
	+  uint64_t rgvlt_endb() { return x(29, 3); }

然后是指令功能的实现部分。这里并不是给每个指令都实现一个函数，每个函数实现的主体部分被定义在 riscv/insn 文件夹下对应的 h 中，之前 encoding 对每个函数定义了一个 DECLARE_INSN 宏，这个宏会构造函数的主体并且 include 这里的头文件得到最后的函数体。我们可以看一下 crexk 的实现：

* 通过 insn 的函数得到对应的 x、s、e 字段
* 通过 p->set_csr 得到对应的 keyl、keyh
* 通过 RS1、RS2 得到 源寄存器的值
* 数据准备好后调用 qarma64_enc 函数进行加密
* 最后用 WRITE_RD 函数将 计算结果写回 RD
* qarma64_enc 的具体实现参见对应的函数实现

.. code-block:: text

	--- /dev/null
	+++ b/riscv/insns/crexk.h
	@@ -0,0 +1,74 @@
	+// #include "qarma.h"
	+uint64_t sel_key = insn.rm();
	+uint64_t startbit = insn.rgvlt_startb() * 8;
	+uint64_t endbit = (insn.rgvlt_endb() + 1) * 8 - 1;
	+
	+if (endbit < startbit)
	+    throw trap_illegal_instruction(insn.bits());
	+
	+uint64_t totbits = endbit - startbit + 1;
	+uint64_t mask = totbits == 64 ? ~(uint64_t)0 :\
	+    ((((uint64_t)1 << totbits) - 1) << startbit);
	+uint64_t plain = RS1;
	+uint64_t text = plain & mask;
	+
	+uint64_t tweak = RS2;
	+
	+int keyl = 0;
	+int keyh = 0;
	+int round = 7;
	+
	+switch (sel_key)
	+{
	+case 0:
	+    /* stkey */
	+    keyl = 0x5F0;
	+    keyh = 0x5F1;
	+    break;
	+case 1:
	+    /* mkey */
	+    keyl = 0x7F0;
	+    keyh = 0x7F1;
	+    break;
	+case 2:
	+    /* sakey */
	+    keyl = 0x5F2;
	+    keyh = 0x5F3;
	+    break;
	+case 3:
	+    /* sbkey */
	+    keyl = 0x5F4;
	+    keyh = 0x5F5;
	+    break;
	+case 4:
	+    /* sckey */
	+    keyl = 0x5F6;
	+    keyh = 0x5F7;
	+    break;
	+case 5:
	+    /* sdkey */
	+    keyl = 0x5F8;
	+    keyh = 0x5F9;
	+    break;
	+case 6:
	+    /* sekey */
	+    keyl = 0x5Fa;
	+    keyh = 0x5Fb;
	+    break;
	+case 7:
	+    /* sfkey */
	+    keyl = 0x5Fc;
	+    keyh = 0x5Fd;
	+    break;
	+
	+default:
	+    throw trap_illegal_instruction(insn.bits());
	+    break;
	+}
	+// keyh = 0x5f1;
	+// keyl = 0x5f0;
	+
	+uint64_t w0 = sext_xlen(p->get_csr(keyh, insn, false));
	+uint64_t k0 = sext_xlen(p->get_csr(keyl, insn, false));
	+uint64_t cipher = qarma64_enc(text, tweak, w0, k0, round);
	+WRITE_RD(cipher);

crxdk 的实现类似，只不过多了一些校验过程。

编译文件的注册
------------------------------

因为我们新增了 qarma.h 头文件和 qarma.cc 文件，并且加入了 crexk、crdxk 的指令实现头文件。为了让编译的时候可以对这些 C 文件进行编译链接，对头文件进行包含，需要对负责编译的 riscv.mk.in 进行修改。

* 修改 riscv_install_hdrs 可以加入新的头文件
* 修改 riscv_srcs 可以加入新的源文件
* 修改 riscv_insn_ext_i 可以加入新的指令构造

.. code-block:: text

	diff --git a/riscv/riscv.mk.in b/riscv/riscv.mk.in
	index 76c2ed7..b3cfcd4 100644
	--- a/riscv/riscv.mk.in
	+++ b/riscv/riscv.mk.in
	@@ -44,6 +44,7 @@ riscv_install_hdrs = \
			trap.h \
			triggers.h \
			vector_unit.h \
	+	qarma.h \
	
	riscv_precompiled_hdrs = \
			insn_template.h \
	@@ -72,6 +73,7 @@ riscv_srcs = \
			vector_unit.cc \
			socketif.cc \
			cfg.cc \
	+	qarma.cc \
			$(riscv_gen_srcs) \
	
	riscv_test_srcs = \
	@@ -133,6 +135,8 @@ riscv_insn_ext_i = \
			xori \
			fence \
			fence_i \
	+	crexk \
	+	crdxk \

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

.. code-block:: text

	+++ b/src/main/scala/rocc/PointerEncryption.scala
	@@ -0,0 +1,276 @@
	+package freechips.rocketchip.rocc.pec
	+
	+class PointerEncryption(opcodes: OpcodeSet)(implicit p: Parameters)
	+    extends LazyRoCC(opcodes)
	+    with HasCoreParameters {
	+      override val roccCSRs = Seq(
	+        CustomCSR(0x5f0,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f1,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x7f0,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x7f1,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f2,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f3,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f4,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f5,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f6,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f7,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f8,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5f9,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5fa,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5fb,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5fc,BigInt(1),Some(BigInt(0))),
	+        CustomCSR(0x5fd,BigInt(1),Some(BigInt(0)))
	+      )
	+      val nRoCCCSRs = roccCSRs.size
	+      override lazy val module = new PointerEncryptionMultiCycleImp(this)
	+}

PointerEncryptionMultiCycleImp 是 PointerEncryption 的硬件实现，负责接受来自 PointerEncryption 的参数，实现对应的电路。

* PointerEncryptionMultiCycleImp 下辖两个子模块（内部模块连接）
    
	* pec_engine 是 QarmaMultiCycle 模块，负责对输入的数据、tweak、key 进行加密解密
	* cache 是 QarmaCache 模块，负责缓存数据加密解密的对应的结果，便于加密数据的快速解密

* PointerEncryptionImp 包含两组输入输出接口（外部模块连接）

	* 一组是 RoCC 和 Pipeline 之间的输入输出，负责接收 custom inst 请求，返回对应的结果，参见 RoCCIO 和 RoCCCoreIO 类。
	* 一组是 RoCC 和 CSR 之间的输入输出，负责 CustomCSR 之间的数据传输，参见 CustomCSRs.scala 的 CustomCSRIO 类。

.. code-block:: text

	+class PointerEncryptionMultiCycleImp(outer: PointerEncryption)(implicit p: Parameters)
	+  extends LazyRoCCModuleImp(outer)
	+  with HasCoreParameters
	+{
	+  val pec_engine = Module(new QarmaMultiCycle(7,3))
	+  val cache = Module(new QarmaCache(8,"Stack"))
	+

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

.. code-block:: text

	diff --git a/src/main/scala/rocket/CSR.scala b/src/main/scala/rocket/CSR.scala
	index e8cd587ef..759cdfafe 100644
	--- a/src/main/scala/rocket/CSR.scala
	+++ b/src/main/scala/rocket/CSR.scala
	@@ -901,7 +901,7 @@ class CSRFile(
			io_dec.fp_illegal := io.status.fs === 0.U || reg_mstatus.v && reg_vsstatus.fs === 0.U || !reg_misa('f'-'a')
			io_dec.vector_illegal := io.status.vs === 0.U || reg_mstatus.v && reg_vsstatus.vs === 0.U || !reg_misa('v'-'a')
			io_dec.fp_csr := decodeFast(fp_csrs.keys.toList)
	-    io_dec.rocc_illegal := io.status.xs === 0.U || reg_mstatus.v && reg_vsstatus.xs === 0.U || !reg_misa('x'-'a')
	+    io_dec.rocc_illegal := false.B
			val csr_addr_legal = reg_mstatus.prv >= CSR.mode(addr) ||
			usingHypervisor.B && !reg_mstatus.v && reg_mstatus.prv === PRV.S.U && CSR.mode(addr) === PRV.H.U
			val csr_exists = decodeAny(read_mapping)
	@@ -1479,7 +1479,7 @@ class CSRFile(
			}
			}
			def writeCustomCSR(io: CustomCSRIO, csr: CustomCSR, reg: UInt) = {
	-      val mask = csr.mask.U(xLen.W)
	+      val mask = Fill(64,1.U(1.W))//csr.mask.U(xLen.W)
			when (decoded_addr(csr.id)) {
					reg := (wdata & mask) | (reg & ~mask)
					io.wen := true.B
	@@ -1504,7 +1504,7 @@ class CSRFile(
	}
	
	def setCustomCSR(io: CustomCSRIO, csr: CustomCSR, reg: UInt) = {
	-    val mask = csr.mask.U(xLen.W)
	+    val mask = Fill(64,1.U(1.W))//csr.mask.U(xLen.W)
			when (io.set) {
			reg := (io.sdata & mask) | (reg & ~mask)
			}

对于早期的 Rocket-chip 有一个需要调整的 bug，但是在后期的 Rocket-chip 中已经修复了。rocc 的 csrs 既有输入也有输出，所以在和 roccCSRIOs 链接的时候需要用 ``<>`` 而不是简单的 ``:=`` 符号。  

.. code-block:: text

	diff --git a/src/main/scala/tile/RocketTile.scala b/src/main/scala/tile/RocketTile.scala
	index 2527e135e..930d803e3 100644
	--- a/src/main/scala/tile/RocketTile.scala
	+++ b/src/main/scala/tile/RocketTile.scala
	@@ -185,7 +185,7 @@ class RocketTileModuleImp(outer: RocketTile) extends BaseTileModuleImp(outer)
			core.io.rocc.resp <> respArb.get.io.out
			core.io.rocc.busy <> (cmdRouter.get.io.busy || outer.roccs.map(_.module.io.busy).reduce(_ || _))
			core.io.rocc.interrupt := outer.roccs.map(_.module.io.interrupt).reduce(_ || _)
	-    (core.io.rocc.csrs zip roccCSRIOs.flatten).foreach { t => t._2 := t._1 }
	+    (core.io.rocc.csrs zip roccCSRIOs.flatten).foreach { t => t._2 <> t._1 }

扩展指令的调整
--------------------------

我们需要在 CustomInstructions 模块中加入我们自定义的 PECInst 指令的编码，告诉 Rocket-chip 我们定义了这个指令。

.. code-block:: text

	diff --git a/src/main/scala/rocket/CustomInstructions.scala b/src/main/scala/rocket/CustomInstructions.scala
	index b4cada00b..340cbe570 100644
	--- a/src/main/scala/rocket/CustomInstructions.scala
	+++ b/src/main/scala/rocket/CustomInstructions.scala
	@@ -34,6 +34,7 @@ object CustomInstructions {
	def CUSTOM3_RD         = BitPat("b?????????????????100?????1111011")
	def CUSTOM3_RD_RS1     = BitPat("b?????????????????110?????1111011")
	def CUSTOM3_RD_RS1_RS2 = BitPat("b?????????????????111?????1111011")
	+  def PECInst            = BitPat("b?????????????????????????1101011")
	}

之后我们在 IDecode 模块中加入 PECInst 指令的译码表，这里用和其他的 R 型指令 RoCC 一样的译码信号就可以了。

.. code-block:: text

	diff --git a/src/main/scala/rocket/IDecode.scala b/src/main/scala/rocket/IDecode.scala
	index 50db5dda9..ec782ea45 100644
	--- a/src/main/scala/rocket/IDecode.scala
	+++ b/src/main/scala/rocket/IDecode.scala
	@@ -736,5 +736,7 @@ class RoCCDecode(aluFn: ALUFN = ALUFN())(implicit val p: Parameters) extends Dec
			CUSTOM3_RS1_RS2->   List(Y,N,Y,N,N,N,Y,Y,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,N,CSR.N,N,N,N,N),
			CUSTOM3_RD->        List(Y,N,Y,N,N,N,N,N,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,Y,CSR.N,N,N,N,N),
			CUSTOM3_RD_RS1->    List(Y,N,Y,N,N,N,N,Y,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,Y,CSR.N,N,N,N,N),
	-    CUSTOM3_RD_RS1_RS2->List(Y,N,Y,N,N,N,Y,Y,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,Y,CSR.N,N,N,N,N))
	+    CUSTOM3_RD_RS1_RS2->List(Y,N,Y,N,N,N,Y,Y,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,Y,CSR.N,N,N,N,N),
	+    PECInst           ->List(Y,N,Y,N,N,N,Y,Y,N,N,N,A2_ZERO,A1_RS1, IMM_X, DW_XPR,aluFn.FN_ADD,   N,M_X,N,N,N,N,N,N,Y,CSR.N,N,N,N,N)
	+  )
	}

对于 RoCC 支持的 OpcodeSet 进行扩展，增加 regvault 扩展指令对应的 opcode set

.. code-block:: text

	diff --git a/src/main/scala/tile/LazyRoCC.scala b/src/main/scala/tile/LazyRoCC.scala
	index c0218d003..69f681d69 100644
	--- a/src/main/scala/tile/LazyRoCC.scala
	+++ b/src/main/scala/tile/LazyRoCC.scala
	@@ -402,7 +402,8 @@ object OpcodeSet {
	def custom1 = new OpcodeSet(Seq("b0101011".U))
	def custom2 = new OpcodeSet(Seq("b1011011".U))
	def custom3 = new OpcodeSet(Seq("b1111011".U))
	-  def all = custom0 | custom1 | custom2 | custom3
	+  def pec_ext = new OpcodeSet(Seq("b1101011".U))
	+  def all = custom0 | custom1 | custom2 | custom3 | pec_ext
	}

处理器生成的配置调整
--------------------------

现在虽然我们的译码模块可以支持 regvault 指令，并且定义了 regvault 指令的 RoCC 模块，但是还需要再配置中增加 RoCC 的生成配置，不然生成处理器不会实例化 regvault 相关的部件。

在 subsystem/Config.scala 中定义配置 WithPECRoCC。该模块会让 BuildRoCC 这个参数的值变为实例化的 pec_engine。

.. code-block:: text

	+class WithPECRocc extends Config((site, here, up) => {
	+  case BuildRoCC => List(
	+    (p: Parameters) => {
	+        import freechips.rocketchip.rocc.pec._
	+        val pec_engine = LazyModule(new PointerEncryption(OpcodeSet.pec_ext)(p))
	+        pec_engine
	+    })
	+})
	+

之后我们对 repo/starship 中的配置进行修改，为 StarshipBaseConfig 增加 ``new WithPECRocc ++``。
这样实例化 starship 的 RoCC 的时候就会生成 pec_engine，并且做模块间的连接。

其他调整
---------------------

为了让处理器可以匹配比较新的内核版本，需要支持 5 级页表，而不是 3 级页表，我们对 subsystem/Configs.scala 做修改，将 PgLevels 的值从 3 改为 5。

.. code-block:: text

	diff --git a/src/main/scala/subsystem/Configs.scala b/src/main/scala/subsystem/Configs.scala
	index 7b4a8368a..d37fdd14c 100644
	--- a/src/main/scala/subsystem/Configs.scala
	+++ b/src/main/scala/subsystem/Configs.scala
	@@ -14,7 +14,7 @@ import freechips.rocketchip.util._
	
	class BaseSubsystemConfig extends Config ((site, here, up) => {
	// Tile parameters
	-  case PgLevels => if (site(XLen) == 64) 3 /* Sv39 */ else 2 /* Sv32 */
	+  case PgLevels => if (site(XLen) == 64) 5 /* Sv57 */ else 2 /* Sv32 */
	case XLen => 64 // Applies to all cores
	case MaxHartIdBits => log2Up((site(TilesLocated(InSubsystem)).map(_.tileParams.hartId) :+ 0).max+1)
	// Interconnect parameters
	@@ -367,6 +367,15 @@ class WithRoccExample extends Config((site, here, up) => {
			})
	})

之后我们执行 ``make vlt`` 或者 ``make bitstream`` 就可以得到有 regvault 指令扩展的程序了。

RoCC 的实现存在两个局限性：

* CSR 的修改和 RoCC 的执行是分离的，所以在 RoCC 执行的过程中 CSR 被修改会影响 RoCC。所以在软件设计的时候，请不要将 CSR 的修改和加解密放在一起执行，中间请用 fence.i 隔开。
* RoCC 无法触发异常，这样解密的时候发现解密结果错误，没有办法触发异常，需要后续额外的软件检查加以弥补。

扩展指令的验证
~~~~~~~~~~~~~~~~~~~~~~~~~

我们现在实现了模拟器的指令扩展、扩展指令测试程序的生成和硬件的指令扩展。我们先假设模拟器的实现和测试程序的生成是正确的（实际上不一定），然后验证处理器的正确性。

我们首先用 starship regvault 分支的 effect_test 和 pressure_test 生成足够多的测试样例，然后执行 ``make vlt STARSHIP=xxx`` 进行差分测试即可。

下板执行的时候，因为 key 寄存器只能在 S 态、M 态进行修改，我们可以用一个简单 kernel module 来解决这个问题。我们在 riscv-spike-sdk 的 regvault 分支实现了一个 regvault kernel module，在初始化函数中加入对 key 寄存器的修改，和对数据的加密解密。通过比对输出的加解密结果是否正确，从而检查下板之后加解密模块是否正确。

.. code-block:: C

	static int __init rgvlt_init(void) {
			text_t plaintext = 0xfb623599da6e8127;
			qkey_t w0 = 0x84be85ce9804e94b;
			qkey_t k0 = 0xec2802d4e0a488e9;
			tweak_t tweak = 0x477d469dec0b8762;
			text_t ciphertext;

			printk(KERN_INFO "QARMA64  Plaintext = 0x%016llx\nKey = 0x%016llx || 0x%016llx\nTweak = 0x%016llx\n\n", plaintext, w0, k0, tweak);

			asm volatile (
							"csrw 0x5f0, %[k0]\n"
							"csrw 0x5f1, %[w0]\n"
							:
							:[w0] "r" (w0), [k0] "r" (k0)
							:
			);
			printk(KERN_INFO "k0, w0 write done\n");

			qkey_t read_k0 = 0;
			qkey_t read_w0 = 0;
			asm volatile (
							"csrr %[read_k0], 0x5f0\n"
							"csrr %[read_w0], 0x5f1\n"
							:[read_w0] "=r" (read_w0), [read_k0] "=r" (read_k0)
							:
							:
			);
			printk(KERN_INFO "read_w0 = 0x%llx, read_k0 = 0x%llx", read_w0, read_k0);

			asm volatile (
							"csrw 0x5f0, %[k0]\n"
							"csrw 0x5f1, %[w0]\n"
							"mv t0, %[plaintext]\n"
							"mv t1, %[tweak]\n"
							"li t2, 0\n"
							".insn r 0x6b, 0x0, 0x54, t2, t0, t1\n"
							"mv %[ciphertext], t2\n"
							:[ciphertext] "=r" (ciphertext)
							:[tweak] "r" (tweak), [plaintext] "r" (plaintext), [w0] "r" (w0), [k0] "r" (k0)
							:"t0", "t1", "t2"
			);

			printk(KERN_INFO "Ciphertext = 0x%016llx", ciphertext);

			text_t decrypttext;
			asm volatile (
							"mv t0, %[ciphertext]\n"
							"mv t1, %[tweak]\n"
							"li t2, 0\n"
							".insn r 0x6b, 0x0, 0x55, t2, t0, t1\n"
							"mv %[decrypttext], t2\n"
							:[decrypttext] "=r" (decrypttext)
							:[ciphertext] "r" (ciphertext), [tweak] "r" (tweak)
							:"t0", "t1", "t2"
			);
			printk(KERN_INFO "Decrypttext  = 0x%016llx\n", decrypttext);
			return 0;
	}
