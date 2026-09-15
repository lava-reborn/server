class lol.events.TimeBarEvent
{
   var param;
   var type;
   static var AIM = "AIM";
   static var RELOAD = "RELOAD";
   static var RELOAD_SREVER = "RELOAD_SREVER";
   static var RELOAD_ACK = "RELOAD_ACK";
   static var UNLOAD = "UNLOAD";
   static var HEAL = "HEAL";
   static var END_HEAL = "END_HEAL";
   static var STRIKE = "STRIKE";
   static var SHOT = "SHOT";
   function TimeBarEvent(_type, _param)
   {
      this.type = _type;
      this.param = _param;
   }
}
