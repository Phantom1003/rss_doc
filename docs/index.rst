Welcome to the documentation site for the RISC-V Spike SDK!
===========================================================

When conducting research on computer architecture today, particularly hardware-assisted design, it is commonplace to make alterations to the entire system stack.
This includes the circuits, simulators, compilers, firmware, operating systems, and user applications.
Unfortunately, a major challenge is the maintenance of the customized system, a.k.a. reproducibility.
Frequently, these modifications cannot be integrated into the upstream, which is continuously evolving.
As a result, maintaining a customized system can be a daunting task.

The **R**\ I\ **S**\ C-V **S**\ pike SDK (RSS) is a software development toolkit designed to facilitate the testing of Linux applications on the official ISA simulator, Spike.
Spike is the simplest simulator that provides clear instructions and allows users to quickly test their ideas.
However, existing tutorials for running Linux on Spike use static compiled busybox, which is not ideal for application testing.
With RSS, users can access scripts and configurations that build a real-world Linux environment for RISC-V embedded systems, allowing them to focus exclusively on project-specific components.
Furthermore, the images provided by RSS can be used on QEMU and FPGA prototype systems.

In addition to the basic usage guidelines, this document will also cover instructions for customizing the simulator, operating system, and toolchain.
We hope that RSS can assist you in exploring the mystery computer system and conducting your fancy research!

Table of Contents
-----------------

.. toctree::
   :maxdepth: 3
   :numbered:

   Internal/index
   Customization/index

