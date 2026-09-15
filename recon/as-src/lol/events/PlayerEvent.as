class lol.events.PlayerEvent
{
   var player;
   var type;
   static var UPDATE_INFO = "uiUpd";
   static var UPDATE_STATE = "userUpdate";
   static var UPDATE_PARAMS = "rp_info";
   static var UPDATE_EFFECTS = "e_list";
   static var NEED_OPEN_FXPAN = "needOpenFXPan";
   static var NEW_DEBUFF_EFFECT = "New debuff";
   static var UPDATE_ONE_EFFECT = "UPDATE_ONE_EFFECT";
   static var DAMAGE = "DAMAGE";
   static var SDAMAGE = "SDAMAGE";
   static var PREPARE = "PREPARE";
   function PlayerEvent(_type, _player)
   {
      this.type = _type;
      this.player = _player;
   }
}
