import jetbrains.buildServer.configs.kotlin.v2019_2.*
import jetbrains.buildServer.configs.kotlin.v2019_2.buildSteps.script
import jetbrains.buildServer.configs.kotlin.v2019_2.triggers.vcs
import jetbrains.buildServer.configs.kotlin.v2019_2.vcs.GitVcsRoot

/*
The settings script is an entry point for defining a TeamCity
project hierarchy. The script should contain a single call to the
project() function with a Project instance or an init function as
an argument.

VcsRoots, BuildTypes, Templates, and subprojects can be
registered inside the project using the vcsRoot(), buildType(),
template(), and subProject() methods respectively.
*/

version = "2023.05"

project {
    // Project configuration
    description = "Untestables - A tool to find repositories that need unit tests"

    // VCS Root configuration
    vcsRoot(UntestablesVcs)

    // Build configuration
    buildType(UntestablesTests)
}

object UntestablesVcs : GitVcsRoot({
    name = "Untestables Git Repository"
    url = "https://github.com/llbbl/untestables.git"
    branch = "refs/heads/main"
    branchSpec = "+:refs/heads/*"
})

object UntestablesTests : BuildType({
    name = "Run Tests"
    description = "Run unit tests for the Untestables project"

    vcs {
        root(UntestablesVcs)
    }

    triggers {
        vcs {
            // Trigger build on each VCS change
            branchFilter = "+:*"
        }
    }

    steps {
        // Set up Python 3.11
        script {
            name = "Set up Python 3.11"
            scriptContent = """
                #!/bin/bash
                
                # Check if Python 3.11 is available
                if command -v python3.11 &>/dev/null; then
                    echo "Python 3.11 is already installed"
                else
                    echo "Installing Python 3.11"
                    # This will vary depending on the OS of your build agent
                    # For Ubuntu:
                    apt-get update
                    apt-get install -y python3.11 python3.11-venv python3.11-dev
                fi
                
                # Create a symlink to ensure python3 points to python3.11
                ln -sf /usr/bin/python3.11 /usr/local/bin/python3
                
                # Verify Python version
                python3 --version
            """.trimIndent()
        }
        
        // Install Poetry
        script {
            name = "Install Poetry"
            scriptContent = """
                #!/bin/bash
                
                # Install Poetry
                curl -sSL https://install.python-poetry.org | python3 -
                
                # Add Poetry to PATH
                export PATH="$HOME/.local/bin:$PATH"
                
                # Verify Poetry installation
                poetry --version
            """.trimIndent()
        }
        
        // Install dependencies
        script {
            name = "Install dependencies"
            scriptContent = """
                #!/bin/bash
                
                # Add Poetry to PATH
                export PATH="$HOME/.local/bin:$PATH"
                
                # Install dependencies including dev dependencies
                poetry install --with dev
            """.trimIndent()
        }
        
        // Run tests
        script {
            name = "Run tests"
            scriptContent = """
                #!/bin/bash
                
                # Add Poetry to PATH
                export PATH="$HOME/.local/bin:$PATH"
                
                # Run tests
                poetry run tests
            """.trimIndent()
        }
    }
    
    // Requirements for the build agent
    requirements {
        // Require a Linux agent
        contains("teamcity.agent.jvm.os.name", "Linux")
    }
})