RISC-V Customization
===========================

ISA Customization
---------------------------

RISC-V is designed to be highly modular and customizable, allowing designers to create custom processor implementations tailored to specific applications and requirements.
The modularity of RISC-V comes from its encoding scheme, which divides instructions into different groups and provides various optional extensions that can be added to the base ISA.
RISC-V provides a "reserved" opcode space, which allows you to create custom instructions.
Althougn you can use any opcodes, to avoid conflicts with future standard extensions, you should use the reserved custom opcode space to create your custom instructions.

.. pdfview:: ../_pdf/unpriv-isa-asciidoc.pdf 131
  :align: center
  :name: custom_opcode_space
  :left: 0.074
  :upper: 0.218
  :right: 0.926
  :lower: 0.448
  :width: 80%

  Unprivileged ISA Specification, Table 35

From the :numref:`custom_opcode_space`, we can find that the reserved opcodes for custom instructions are:

* **custom-0**: ``0b000_1011``, ``0x0b``
* **custom-1**: ``0b010_1011``, ``0x2b``
* **custom-2**: ``0b101_1011``, ``0x5b``
* **custom-3**: ``0b111_1011``, ``0x7b``

Some projects have already used these custom opcodes, such as Rocket Chip.
Rocket core provides a set of custom instructions, the Rocket Chip Coprocessor (ROCC) instruction extension, for accelerators.

The RoCC instructions follow a format similar to the R-type format, but the `funct3` section is divided into three distinct functional fields.

.. code-block:: text

   31      25 24  20 19  15 14  13  12  11  7 6    0
  ┌──────────┬──────┬──────┬───┬───┬───┬─────┬──────┐
  │  funct7  │ rs2  │ rs1  │ xd│xs1│xs2│ rd  │opcode│
  └──────────┴──────┴──────┴───┴───┴───┴─────┴──────┘

..

* ``xd`` bit is used to indicate whether the instruction writes a destination register.
* ``xs1`` and ``xs2`` bits are used to indicate whether the instruction reads source registers.

In cases where an instruction does not use source and destination registers, the corresponding register index fields can encode other information, which deviates from the standard RISC-V R-type instruction format.

Here we provide the ROCC example to demonstrate that the format of a custom instruction is not restricted to the standard instruction format.
As you create your own custom instruction, you have the freedom to define the format in any way you prefer.
However, it is crucial to thoughtfully and reasonably plan each instruction bit.
When assigning functionality to a bit, it is crucial to consider how it will impact the circuit and architecture.


CSR Customization
------------------------

The specification also reserves a few CSR address spaces for custom purposes.
You might find it useful to customize the CSR to store certain states.


.. pdfview:: ../_pdf/priv-isa-asciidoc.pdf 15
  :align: center
  :name: custom_csr_space
  :left: 0.214
  :upper: 0.165
  :right: 0.788
  :lower: 0.340
  :width: 60%
  
  Privileged ISA Specification, Table 3-4

Generally, the address of a CSR determines its permission and accessibility.
The RISC-V ISA specification defines a CSR address mapping convention.
For a CSR address (csr[11:0]), the top two bits (csr[11:10]) indicate if the register is read/write (00, 01, or 10) or read-only (11). The following two bits (csr[9:8]) encode the lowest privilege level that can access the CSR.
Some designs may follow this convention, so if you extend custom CSRs on these designs, you should carefully choose the address of your new CSRs.


riscv-opcodes
-------------

The RISC-V community offers a helpful tool called `riscv-opcodes <https://github.com/riscv/riscv-opcodes>`_ that can generate opcode decoders for various purposes including documents, simulations, and circuits.
We highly recommend that you utilize this tool to create the opcode decoder for your customized instructions.
It's important to note that if you choose to self-maintain your opcode, there may be unexpected bugs due to potential incompatible changes in the upstream specification.

The files named ``rv*`` in the root directory, as well as the ``unratified`` directory, maintain the format of each instruction.

To illustrate how to define an instruction, let's take the ``addi`` instruction from ``rv_i`` as an example.
This is an I-type instruction with ``rd``, ``rs1``, and ``imm12`` fields, and its opcode is ``0x13``.
Therefore, the definition of ``addi`` is as follows:

.. code-block:: text

  addi    rd rs1 imm12           14..12=0 6..2=0x04 1..0=3

As you can see, the definition is straightforward.
You can find more descriptions about the syntax in the official ``README``.
Next, we move on to define our custom instruction.

First, RegVault has really different instruction formats from the standard RISC-V instruction formats.
So, we need to define the new instruction fields for the range selection fields.

In order to implement RegVault, we require three 5-bit fields to indicate the indexes of the plaintext, tweak, and ciphertext registers.
As RegVault is a 64-bit RISC-V instruction extension, we need two additional 3-bit fields to encode the starting byte and ending byte, respectively.
Additionally, we plan to offer 8 key registers, so we also require 3 bits to encode the key register.

.. code-block:: text

  TODO: 
    1. add new fields in arg_lut.csv
    2. define new instruction format
    3. define new csr in csrs.csv

After defining the new instruction format, we can generate the opcode decoder by running ``make``.
The generated ``encoding.out.h`` file will contain the new instructions and CSRs.

.. code-block:: text

  TODO: 
    list generated instruction and CSR macors
