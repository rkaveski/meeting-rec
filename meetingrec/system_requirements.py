import subprocess
import os
import shutil
import rumps

from typing import Dict


class SystemRequirements:
    """Verifies and helps install system requirements for MeetingRec."""

    @staticmethod
    def check_homebrew_installed() -> bool:
        """Check if Homebrew is installed."""
        return shutil.which('brew') is not None
    
    @staticmethod
    def install_homebrew() -> bool:
        """Provide instructions to install Homebrew."""
        response = rumps.alert(
            "Homebrew Required",
            "MeetingRec requires Homebrew to install system dependencies. "
            "Would you like to install it now?",
            "Install Homebrew", "Cancel"
        )
        
        if response == 1:  # User clicked "Install Homebrew"
            homebrew_install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            os.system(f"open -a Terminal.app && osascript -e 'tell application \"Terminal\" to do script \"{homebrew_install_cmd}\"'")
            return True
        return False
    
    @staticmethod
    def check_dependency_installed(dependency: str) -> bool:
        """Check if a Homebrew dependency is installed."""
        try:
            result = subprocess.run(
                ['brew', 'list', dependency], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def install_dependency(dependency: str) -> bool:
        """Install a dependency via Homebrew."""
        try:
            response = rumps.alert(
                f"Install {dependency}",
                f"MeetingRec requires {dependency}. Would you like to install it now?",
                "Install", "Cancel"
            )
            
            if response == 1:  # User clicked "Install"
                install_cmd = f"brew install {dependency}"
                os.system(f"open -a Terminal.app && osascript -e 'tell application \"Terminal\" to do script \"{install_cmd}\"'")
                return True
            return False
        except Exception as e:
            print(f"Error installing {dependency}: {e}")
            return False
    
    def verify_all_requirements(self) -> Dict[str, bool]:
        """Verify all system requirements and return status."""
        requirements = {
            "homebrew": self.check_homebrew_installed(),
            "portaudio": False,
            "blackhole-2ch": False,
            "ffmpeg": False
        }
        
        # If Homebrew is not installed, attempt to install it
        if not requirements["homebrew"]:
            requirements["homebrew"] = self.install_homebrew()
            if not requirements["homebrew"]:
                return requirements  # Can't proceed without Homebrew
        
        # Check and offer to install other dependencies
        for dep in ["portaudio", "blackhole-2ch", "ffmpeg"]:
            requirements[dep] = self.check_dependency_installed(dep)
            if not requirements[dep]:
                requirements[dep] = self.install_dependency(dep)
        
        return requirements


def verify_system_requirements() -> bool:
    """Entry point to verify all system requirements."""
    checker = SystemRequirements()
    results = checker.verify_all_requirements()
    
    # Check if all requirements are met
    if all(results.values()):
        return True
    
    # Show missing requirements
    missing = [req for req, installed in results.items() if not installed]
    if missing:
        rumps.alert(
            "Missing Requirements",
            f"The following requirements are missing and required for full functionality: {', '.join(missing)}.\n\n"
            "Please install them manually and restart the application.",
            "OK"
        )
    
    return False