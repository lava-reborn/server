class lol.server.mess.CSM_QDynInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QDynInfo(q_id)
   {
      super();
      this._name = "q_di";
      this.addProp("q_id",q_id);
   }
}
