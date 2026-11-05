# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.10)
project(drop_hash CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_library(drop_hash drop_hash.cpp)
target_include_directories(drop_hash PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
add_executable(drop_hash_cli drop_hash_cli.cpp)
target_link_libraries(drop_hash_cli drop_hash)
