#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <processthreadsapi.h>
#include <tlhelp32.h>
#include <shlobj.h>
#include <windows.h>

namespace fs = std::filesystem;

enum exit_code : int {
    EXIT_OK = 0,
    ERR_DLL_NOT_FOUND = 1,
    ERR_PROCESS_NOT_FOUND = 2,
    ERR_INJECT_FAILED = 3,
};

void show_msgbox(const char* title, const char* message) {
    MessageBoxA(NULL, message, title, MB_OK | MB_ICONERROR);
}

DWORD find_process_id(const char* process_name) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return 0;
    }

    PROCESSENTRY32 entry = {};
    entry.dwSize = sizeof(PROCESSENTRY32);

    if (!Process32First(snapshot, &entry)) {
        CloseHandle(snapshot);
        return 0;
    }

    do {
        if (strcmp(process_name, entry.szExeFile) == 0) {
            DWORD pid = entry.th32ProcessID;
            CloseHandle(snapshot);
            return pid;
        }
    } while (Process32Next(snapshot, &entry));

    CloseHandle(snapshot);
    return 0;
}

fs::path get_app_data() {
    PWSTR path = nullptr;
    HRESULT result = SHGetKnownFolderPath(FOLDERID_RoamingAppData, 0, nullptr, &path);

    if (result != S_OK || !path) {
        if (path) {
            CoTaskMemFree(path);
        }
        return fs::path();
    }

    fs::path app_data(path);
    CoTaskMemFree(path);
    return app_data;
}

exit_code inject_dll(const std::wstring& dll_path) {
    DWORD pid = find_process_id("RocketLeague.exe");

    if (pid == 0) {
        show_msgbox("error", "rocket League process not found.");
        return ERR_PROCESS_NOT_FOUND;
    }

    auto flags = PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ;
    HANDLE process = OpenProcess(flags, FALSE, pid);

    if (!process) {
        show_msgbox("error", "failed to open rocket league process.");
        return ERR_PROCESS_NOT_FOUND;
    }

    LPVOID load_library_addr = (LPVOID)GetProcAddress(
        GetModuleHandleW(L"kernel32.dll"),
        "LoadLibraryW"
    );

    if (!load_library_addr) {
        CloseHandle(process);
        return ERR_INJECT_FAILED;
    }

    size_t path_size = (dll_path.length() + 1) * sizeof(wchar_t);
    LPVOID remote_memory = VirtualAllocEx(
        process,
        NULL,
        path_size,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE
    );

    if (!remote_memory) {
        CloseHandle(process);
        return ERR_INJECT_FAILED;
    }

    if (!WriteProcessMemory(process, remote_memory, dll_path.c_str(), path_size, NULL)) {
        VirtualFreeEx(process, remote_memory, 0, MEM_RELEASE);
        CloseHandle(process);
        return ERR_INJECT_FAILED;
    }

    HANDLE thread = CreateRemoteThread(
        process,
        NULL,
        0,
        (LPTHREAD_START_ROUTINE)load_library_addr,
        remote_memory,
        0,
        NULL
    );

    if (!thread) {
        VirtualFreeEx(process, remote_memory, 0, MEM_RELEASE);
        CloseHandle(process);
        return ERR_INJECT_FAILED;
    }

    WaitForSingleObject(thread, INFINITE);

    DWORD exit_status = 0;
    GetExitCodeThread(thread, &exit_status);

    VirtualFreeEx(process, remote_memory, 0, MEM_RELEASE);
    CloseHandle(thread);
    CloseHandle(process);

    return exit_status != 0 ? EXIT_OK : ERR_INJECT_FAILED;
}

int main() {
    fs::path dll_path = get_app_data() / "bakkesmod/bakkesmod/dll/bakkesmod.dll";

    if (!fs::exists(dll_path)) {
        show_msgbox("DLL nt found", "could not find bakkesmod.dll...");
        return ERR_DLL_NOT_FOUND;
    }

    return inject_dll(dll_path.wstring());
}
