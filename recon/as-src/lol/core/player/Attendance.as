class lol.core.player.Attendance
{
   var _desc;
   var _name;
   var id;
   var mob_id;
   static var SET_HOME = 0;
   static var HEAL = 1;
   static var BANK = 2;
   function Attendance(_id, m_id)
   {
      this.id = _id;
      this.mob_id = m_id;
      this.init(this.id);
   }
   function init(id)
   {
      var _loc2_;
      var _loc3_;
      switch(id)
      {
         case lol.core.player.Attendance.SET_HOME:
            this._name = "Прописка";
            this._desc = "В этой локации вы будете возрождаться в случае смерти";
            return;
         case lol.core.player.Attendance.HEAL:
            this._name = "Лечение";
            _loc2_ = lol.core.player.Healer(lol.core.Master.getInstance().getPlayer(this.mob_id)).getMedPrice();
            _loc3_ = _loc2_.moneyType != lol.data.Money.AFRO ? "голда" : "афро";
            this._desc = "Персонаж может вылечить Вас за сумму " + _loc2_.moneyValue + " " + _loc3_;
            return;
         default:
            this._name = "";
            this._desc = "";
            return;
      }
   }
   function activate()
   {
      var _loc2_ = new lol.server.mess.CSM_Conv(this.mob_id,this.id);
      if(lol.server.XMLConnection.getInstance().Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cmdAck);
      }
   }
   function cmdAck(obj)
   {
   }
   function get name()
   {
      return this._name;
   }
   function get description()
   {
      return this._desc;
   }
}
