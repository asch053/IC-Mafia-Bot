# test_imports.py

from discord.ext import commands, tasks

print(f"commands: {commands}")  # Check if commands is imported
print(f"tasks: {tasks}")       # Check if tasks is imported

@tasks.loop(seconds=1)  # Use tasks directly
async def my_task():
    print("Task running")

# We *don't* need to start the loop for this test,
# just see if we can *define* the task.

# If you *do* want to see it run, you can add:
# import asyncio
# asyncio.run(my_task.start())