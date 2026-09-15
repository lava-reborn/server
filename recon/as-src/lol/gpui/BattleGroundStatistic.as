class lol.gpui.BattleGroundStatistic extends lol.gpui.GPUIObject
{
   var bg_manager;
   var close_btn;
   var cont;
   var dispatchEvent;
   var scrollPan;
   function BattleGroundStatistic()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.scrollPan.fillContent();
      this.scrollPan.setSize(419,367);
      this.cont = this.scrollPan.content;
      this.bg_manager = lol.core.battlegrounds.BattleGroundManager.getInstance();
      this.initStatistic();
   }
   function kill()
   {
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
   }
   function initStatistic()
   {
      var _loc7_ = lol.core.Master.getInstance();
      this.scrollPan.fillContent();
      this.cont = this.scrollPan.content;
      var _loc3_ = this.bg_manager.bg_results;
      var _loc8_ = 0;
      var _loc2_ = 0;
      var _loc4_;
      var _loc5_;
      var _loc6_;
      while(_loc2_ < _loc3_.length)
      {
         _loc4_ = this.cont.attachMovie("BG_ResultsItem","BG_ResultsItem" + _loc2_,this.cont.getNextHighestDepth());
         _loc4_.id = _loc2_;
         _loc4_._y = _loc8_ * (_loc4_._height + 4);
         _loc5_ = "";
         trace("BattleGroundStatistic -> initStatistic -> bg_results[i].player_id = " + _loc3_[_loc2_].player_id);
         if(_loc3_[_loc2_].player_id == 0)
         {
            _loc5_ = "[" + _loc7_.gamer.attributes.getLevel() + "] " + _loc7_.gamer.playerInfo.name;
         }
         else
         {
            _loc6_ = _loc7_.getPlayer(_loc3_[_loc2_].player_id);
            _loc5_ = "[" + _loc6_.attributes.getLevel() + "] " + _loc6_.playerInfo.name;
         }
         _loc4_.init(_loc5_,_loc3_[_loc2_].kills,_loc3_[_loc2_].deaths,_loc3_[_loc2_].team_id,_loc3_[_loc2_].player_id == 0);
         _loc8_ = _loc8_ + 1;
         _loc2_ = _loc2_ + 1;
      }
      this.scrollPan.setPosition(0,0);
   }
   function exitBattleGround()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
      this.bg_manager.exitFromBattleGround(true);
      this.bg_manager.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      this.dispatchEvent({type:"closeWindow"});
   }
   function close()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
      this.bg_manager.exitFromBattleGround(true);
      this.bg_manager.BG_Status = lol.core.battlegrounds.BattleGroundManager.BG_CLIENT_STATUS_IDLE;
      lol.core.SceneShifter.hotKeyManager.enabled = true;
      this.dispatchEvent({type:"closeWindow"});
   }
}
