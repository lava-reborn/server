class lol.gpui.ActionBar extends lol.gpui.GPUIObject
{
   var _x;
   var _y;
   var action_btn;
   var action_disabled;
   var avatarPan;
   var doLater;
   var fire_btn;
   var fire_disabled;
   function ActionBar()
   {
      super();
      this.doLater("_init");
   }
   function init(_playerID, _action, _fire)
   {
      this.avatarPan.playerID = _playerID;
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
      lol.core.SceneShifter.chat.addEventListener("chatRes",this);
      this.action_btn._visible = _action;
      this.action_disabled._visible = !_action;
      this.fire_btn._visible = _fire;
      this.fire_disabled._visible = !_fire;
   }
   function _init()
   {
      this.action_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.action_func);
      this.fire_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.fire_func);
      this.resizeStage({w:Stage.width,h:Stage.height + lol.core.SceneShifter.chat.chatResize._y});
   }
   function kill()
   {
      lol.core.SceneShifter._ref.removeEventListener("resizeStage",this);
      lol.core.SceneShifter.chat.removeEventListener("chatRes",this);
      this.action_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.action_func);
      this.fire_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.fire_func);
   }
   function action_func()
   {
      var _loc1_ = lol.core.Master.getInstance().gamer.contactManager.selectedID;
      lol.core.Master.getInstance().gamer.gotoWalker(_loc1_,"contact");
   }
   function fire_func()
   {
      var _loc1_ = lol.core.Master.getInstance().gamer.contactManager.selectedID;
      lol.core.Master.getInstance().gamer.fire(1,_loc1_);
   }
   function chatRes(obj)
   {
      var _loc2_ = new Object();
      _loc2_.w = Stage.width;
      _loc2_.h = obj.h + 144;
      this.resizeStage(_loc2_);
   }
   function resizeStage(obj)
   {
      this._x = obj.w - 195;
      this._y = obj.h - 305;
   }
}
