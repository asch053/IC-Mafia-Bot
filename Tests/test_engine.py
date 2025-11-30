import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import discord
from game.engine import Game
import config

class TestGameEngine(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Setup mocks
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        
        # Initialize game
        self.game = Game(self.mock_bot, self.mock_guild)
        
        # Mock internal components
        self.game.narration_manager = MagicMock()
        self.game.signup_loop = MagicMock()
        self.game.game_loop = MagicMock()
        
        # Set basic game settings
        self.game.game_settings["game_id"] = "test_game_id"
        self.game.game_settings["phase_number"] = 1
        self.game.game_settings["current_phase"] = "day"

    @patch('game.engine.update_player_discord_roles') 
    async def test_reset_preserves_cosmetic_roles(self, mock_update_roles):
        """Test that reset removes game roles but KEEPS other roles."""
        # Setup
        self.game.players = {123: MagicMock(id=123, is_npc=False)}
        self.game.game_settings["game_started"] = True
        
        # Mock Guild Member
        mock_member = MagicMock()
        
        # --- Create Roles ---
        role_living = MagicMock(id=998, name="Living")
        role_dead = MagicMock(id=999, name="Dead")
        role_spectator = MagicMock(id=997, name="Spectator")
        
        # The roles we want to KEEP
        role_admin = MagicMock(id=111, name="Admin") 
        role_cosmetic = MagicMock(id=222, name="Pretty Pink Color") 
        
        # Give the member: Living + Admin + Cosmetic
        mock_member.roles = [role_living, role_admin, role_cosmetic] 
        
        # Ensure edit is an AsyncMock since it's an async method
        mock_member.edit = AsyncMock()

        # Setup Guild Mocks
        self.mock_guild.get_member.return_value = mock_member
        
        # Mock Guild Roles lookup
        def get_role_side_effect(role_id):
            if role_id == 997: return role_spectator
            return None
        self.mock_guild.get_role.side_effect = get_role_side_effect

        # Mock Config IDs
        self.game.discord_role_data = {
            "spectator": {"id": 997},
            "living": {"id": 998},
            "dead": {"id": 999}
        }

        # --- ACT ---
        await self.game.reset()

        # --- ASSERT ---
        # 1. Check Game State Cleared
        self.assertEqual(len(self.game.players), 0)
        self.assertFalse(self.game.game_settings["game_started"])

        # 2. Capture the arguments passed to member.edit()
        mock_member.edit.assert_called()
        args, kwargs = mock_member.edit.call_args
        new_roles = kwargs['roles']
        
        # 3. Verify Game Roles Removed/Added
        self.assertNotIn(role_living, new_roles, "Living role should be removed")
        self.assertIn(role_spectator, new_roles, "Spectator role should be added")
        
        # 4. Verify Cosmetic/Admin Roles Preserved
        self.assertIn(role_admin, new_roles, "Admin role should be preserved")
        self.assertIn(role_cosmetic, new_roles, "Cosmetic role should be preserved")
        
        # 5. Verify Count (Admin + Cosmetic + Spectator = 3)
        self.assertEqual(len(new_roles), 3, "Should have exactly 3 roles")

    @patch('game.engine.Game._save_game_summary')
    async def test_announce_winner_chunks_messages(self, mock_save):
        """Test that massive status messages are split into chunks."""
        # Setup
        mock_channel = AsyncMock()
        self.mock_bot.get_channel.return_value = mock_channel
        
        # Mock Storyteller response
        self.game.narration_manager.construct_story.return_value = "A great story."

        # Force a HUGE status message (over 2000 chars)
        # 'A' * 1950 is close to limit, adding 'B' * 100 pushes it over
        long_status = "Player Data\n" + ("A" * 1950) + "\n" + ("B" * 100)
        
        # Use patch.object to mock the method on the specific instance
        with patch.object(self.game, 'get_status_message', return_value=long_status):
            await self.game.announce_winner("Town")

        # Assert
        # 1. Verify channel.send was called multiple times
        # (Once for story, and at least twice for the split status)
        self.assertTrue(mock_channel.send.call_count >= 3) 
        
        # 2. Verify content of calls
        call_args_list = mock_channel.send.call_args_list
        
        # First call should be the story
        self.assertIn("Game Over!", call_args_list[0][0][0]) 
        
        # Subsequent calls should contain our status message parts
        # We check that our massive string of 'A's made it into one of the calls
        sent_content_combined = "".join([call[0][0] for call in call_args_list[1:]])
        self.assertIn("AAAAA", sent_content_combined)
        self.assertIn("BBBBB", sent_content_combined)

    async def test_process_lynch_vote_valid(self):
        """Test processing a valid vote."""
        # Setup
        voter = MagicMock(id=1, name="Voter", display_name="VoterName")
        target = MagicMock(id=2, name="Target", display_name="TargetName", is_alive=True)
        
        # Add players to game
        self.game.players[1] = voter
        self.game.players[2] = target
        
        # Setup mocks for attributes that might be accessed
        voter.is_alive = True
        voter.action_target = None
        
        # Mock channel lookup
        mock_channel = AsyncMock()
        self.mock_bot.get_channel.return_value = mock_channel

        # Helper to mock finding player by name
        self.game.get_player_by_name = MagicMock(return_value=target)

        # Act
        interaction = MagicMock() # We don't use interaction in the logic, just pass it
        result = await self.game.process_lynch_vote(interaction, voter, "TargetName")

        # Assert
        self.assertIn("recorded", result)
        self.assertIn(1, self.game.lynch_votes[2]) # Voter ID in Target's list
        self.assertEqual(len(self.game.vote_history), 1) # History updated

if __name__ == '__main__':
    unittest.main()