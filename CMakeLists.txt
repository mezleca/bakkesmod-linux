cmake_minimum_required(VERSION 3.16)

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_C_COMPILER x86_64-w64-mingw32-gcc)
set(CMAKE_CXX_COMPILER x86_64-w64-mingw32-g++)

project(simple_injector VERSION 0.0.1 LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# link the C++ and C standard libraries statically
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -static-libstdc++ -static-libgcc")
set(CMAKE_BUILD_TYPE Release)

# get source files
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS "src/bakkesmod_linux/injector/*.cpp")
file(GLOB_RECURSE HEADERS CONFIGURE_DEPENDS "src/bakkesmod_linux/injector/*.hpp")

# add dependencies
# add_subdirectory(vendor/fmt)

add_executable(${PROJECT_NAME}
    ${SOURCES}
    ${HEADERS}
)

if(DEFINED OUTPUT_NAME)
    set_target_properties(${PROJECT_NAME} PROPERTIES OUTPUT_NAME ${OUTPUT_NAME})
endif()

# target_link_libraries(${PROJECT_NAME} PRIVATE
#     fmt::fmt
# )

# target_include_directories(${PROJECT_NAME} PRIVATE
#     ${CMAKE_CURRENT_SOURCE_DIR}/vendor/...
# )

add_custom_target(copy_compile_commands ALL
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    ${CMAKE_BINARY_DIR}/compile_commands.json
    ${CMAKE_SOURCE_DIR}/compile_commands.json
)
