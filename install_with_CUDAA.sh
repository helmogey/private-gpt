# 1. Install GCC-12 (REQUIRED for CUDA 12.0 compatibility)
# The "_Float32 undefined" error happens because GCC 13+ headers are incompatible with CUDA 12.0.
# You MUST install gcc-12:
# sudo apt update && sudo apt install gcc-12 g++-12 -y

# 2. Fix Linker Paths (CRITICAL for Ubuntu/Debian)
# The linker fails looking for /lib64/libm.so.6, libc.so.6, etc. We must symlink the system libs.
# Check if /lib/x86_64-linux-gnu exists (standard Ubuntu path)
if [ -d "/lib/x86_64-linux-gnu" ]; then
    echo "Creating symlinks for libraries in /lib64 and /usr/lib64..."
    sudo mkdir -p /lib64
    sudo mkdir -p /usr/lib64
    
    # Math libraries
    [ ! -f /lib64/libm.so.6 ] && sudo ln -s /lib/x86_64-linux-gnu/libm.so.6 /lib64/libm.so.6
    [ ! -f /lib64/libmvec.so.1 ] && sudo ln -s /lib/x86_64-linux-gnu/libmvec.so.1 /lib64/libmvec.so.1
    
    # Standard C libraries
    [ ! -f /lib64/libc.so.6 ] && sudo ln -s /lib/x86_64-linux-gnu/libc.so.6 /lib64/libc.so.6
    [ ! -f /usr/lib64/libc_nonshared.a ] && sudo ln -s /usr/lib/x86_64-linux-gnu/libc_nonshared.a /usr/lib64/libc_nonshared.a
fi

# 3. Set Compiler Paths to GCC 12 explicitly
export CC=/usr/bin/gcc-12
export CXX=/usr/bin/g++-12
export CUDAHOSTCXX=/usr/bin/g++-12

# 4. Force the architecture and ALLOW UNSUPPORTED COMPILER
# We use 'native' to auto-detect the GPU (works for A5000, RTX 30xx, 40xx).
# Specific codes: 86 (RTX 30xx/A5000), 89 (RTX 40xx), 90 (H100).
export CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=native -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc -DCMAKE_C_COMPILER=/usr/bin/gcc-12 -DCMAKE_CXX_COMPILER=/usr/bin/g++-12 -DCMAKE_CUDA_FLAGS='-allow-unsupported-compiler'"
export FORCE_CMAKE=1

# 5. Clean install with VERSION CHECK
# Retrieve the currently required version to prevent mismatch:
CURRENT_VERSION=$(pip show llama-cpp-python | grep Version | cut -d ' ' -f 2)

# If CURRENT_VERSION is empty (not installed), check your requirements file.
# Otherwise, force reinstall the SAME version with CUDA support:
if [ -z "$CURRENT_VERSION" ]; then
    echo "Package not found. Installing latest (WARNING: Check compatibility!)"
    pip install llama-cpp-python --no-cache-dir --force-reinstall --verbose
else
    echo "Reinstalling version $CURRENT_VERSION with CUDA support..."
    pip install "llama-cpp-python==$CURRENT_VERSION" --no-cache-dir --force-reinstall --verbose
fi
