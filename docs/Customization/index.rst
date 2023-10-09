Customization
=============

In this section, we will demonstrate how to customize the RISC-V ISA by designing a custom instruction extension called **RegVault** as an example, which is described in paper :footcite:`xu2022regvault`.

The RegVault instruction extension contains two sets of context-aware cryptographic instructions that provide cryptographically strong confidentiality and integrity protection for register-grained data.
The mnemonics for these instructions are listed in the table below:

.. list-table:: RegVault cryptographic primitives
   :widths: 20 35
   :header-rows: 1
   :align: center

   * - Set Name
     - Mnemonic

   * - **c**\ ontext-aware **r**\ egister **e**\ ncrypt
     - ``cre[x]k rd, rs[e:s], rt``

   * - **c**\ ontext-aware **r**\ egister **d**\ ecrypt
     - ``crd[x]k rd[e:s], rs, rt``

* ``cre[x]k rd, rs[e:s], rt`` is the encryption instruction. It selects bytes within range ``[e:s]`` (i.e., s-th to e-th bytes) from source register ``rs`` , encrypts them with the tweak in register ``rt`` and the key in key register ``x``, and puts the ciphertext in destination register ``rd``.

* ``crd[x]k rd[e:s], rs, rt`` is the decryption instruction. It decrypts the value in ``rs`` with given tweak in ``rt`` and key ``x``, and puts the plaintext in ``rd``. Moreover, it checks whether the bytes other than ``[e:s]`` in plaintext remain zero. If not, the integrity check fails and an exception is raised.

To implement the RegVault instruction extension, we need to customize the instruction set architecture (ISA) to support the new instructions, and customize the Control and Status Registers (CSRs) to save the keys.

Next, we will provide step-by-step instructions on the following topics:

.. toctree::
  :maxdepth: 2
  
  RISC-V-Customization
  Spike-Customization


.. footbibliography::
