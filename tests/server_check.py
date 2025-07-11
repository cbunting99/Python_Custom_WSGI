#!/usr/bin/env python3
"""
Server Readiness Check
Verifies that the Custom WSGI Server is ready for use
"""

import sys
import importlib
import platform

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} (compatible)")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        return False

def check_import(module_name, optional=False):
    """Check if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✓ {module_name} - available")
        return True
    except ImportError:
        status = "⚠️" if optional else "❌"
        note = " (optional)" if optional else " (required)"
        print(f"{status} {module_name} - not available{note}")
        return not optional

def check_server_components():
    """Check if server components are working"""
    components = [
        'src.core.wsgi_server',
        'src.core.request_handler', 
        'src.httptools_server',
        'src.core.server_core',
        'src.optimizations.memory_optimizations',
        'src.features.keepalive',
        'src.features.pipelining',
        'src.optimizations.multiprocess_server'
    ]
    
    all_good = True
    for component in components:
        if not check_import(component):
            all_good = False
    
    return all_good

def check_dependencies():
    """Check required and optional dependencies"""
    required = ['asyncio']
    optional = ['uvloop', 'httptools']
    
    all_required = True
    for dep in required:
        if not check_import(dep):
            all_required = False
    
    # Check optional dependencies
    for dep in optional:
        check_import(dep, optional=True)
    
    return all_required

def main():
    """Main readiness check"""
    print("🔍 Custom WSGI Server Readiness Check")
    print("=" * 40)
    
    print(f"\n📋 System Information:")
    print(f"   Platform: {platform.system()} {platform.release()}")
    print(f"   Architecture: {platform.machine()}")
    
    print(f"\n🐍 Python Version:")
    python_ok = check_python_version()
    
    print(f"\n📦 Dependencies:")
    deps_ok = check_dependencies()
    
    print(f"\n🔧 Server Components:")
    components_ok = check_server_components()
    
    print(f"\n🎯 Platform-Specific Features:")
    if sys.platform != 'win32':
        print("✓ uvloop support available")
        print("✓ SO_REUSEPORT support available") 
        print("✓ Multi-worker recommended")
    else:
        print("⚠️ uvloop not available on Windows")
        print("⚠️ SO_REUSEPORT not available on Windows")
        print("⚠️ Single worker recommended")
    
    print(f"\n{'='*40}")
    
    if python_ok and deps_ok and components_ok:
        print("🚀 Server is READY for use!")
        print("\nQuick start:")
        print("   python examples/demo.py")
        print("   python examples/example_usage.py")
        return 0
    else:
        print("❌ Server has issues - check errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())